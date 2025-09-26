using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Data.Sqlite;
using Betfair.AutomatedServices;

namespace Betfair.Services
{
    public class AutomatedMarketSubscriptionService : BackgroundService
    {
        private readonly ILogger<AutomatedMarketSubscriptionService> _logger;
        private readonly IServiceProvider _serviceProvider;
        private readonly string _connectionString;
        private readonly HashSet<string> _subscribedMarkets = new();
        private Timer _subscriptionTimer;

        public AutomatedMarketSubscriptionService(
            ILogger<AutomatedMarketSubscriptionService> logger,
            IServiceProvider serviceProvider,
            Microsoft.Extensions.Configuration.IConfiguration configuration)
        {
            _logger = logger;
            _serviceProvider = serviceProvider;
            // Use the live_betting.sqlite database path
            _connectionString = "Data Source=/Users/clairegrady/RiderProjects/betfair/data-model/live_betting.sqlite";
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("🚀 Automated Market Subscription Service started");

            // Check every 30 seconds for races that need subscription
            _subscriptionTimer = new Timer(async _ => await CheckAndSubscribeToMarkets(), 
                null, TimeSpan.Zero, TimeSpan.FromSeconds(30));

            // Keep the service running
            while (!stoppingToken.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
            }
        }

        private async Task CheckAndSubscribeToMarkets()
        {
            try
            {
                var upcomingRaces = await GetUpcomingRaces();
                
                foreach (var race in upcomingRaces)
                {
                    if (!_subscribedMarkets.Contains(race.MarketId))
                    {
                        await SubscribeToMarket(race.MarketId, race.Venue, race.RaceNumber, race.RaceTime);
                    }
                }

                // Clean up old subscriptions (races that have finished)
                await CleanupOldSubscriptions();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in automated market subscription check");
            }
        }

        private async Task<List<RaceInfo>> GetUpcomingRaces()
        {
            _logger.LogWarning("Automated Market Subscription Service started");
            var races = new List<RaceInfo>();
            var now = DateTime.UtcNow;
            var subscriptionWindow = TimeSpan.FromMinutes(15); // Subscribe 15 minutes before race

            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            // Get races from race_times that are starting soon
            var raceTimesQuery = @"
                SELECT venue, race_number, race_time, race_date
                FROM race_times 
                WHERE datetime(race_time) BETWEEN datetime('now') AND datetime('now', '+1 hour')
                ORDER BY race_time";

            using var raceTimesCommand = new SqliteCommand(raceTimesQuery, connection);
            using var raceTimesReader = await raceTimesCommand.ExecuteReaderAsync();

            while (await raceTimesReader.ReadAsync())
            {
                var venue = raceTimesReader.GetString(1); // venue column
                var raceNumber = raceTimesReader.GetInt32(2); // race_number column
                var raceTimeStr = raceTimesReader.GetString(3); // race_time column
                var raceDate = raceTimesReader.GetString(4); // race_date column

                if (DateTime.TryParse(raceTimeStr, out var raceTime))
                {
                    var timeUntilRace = raceTime - now;
                    
                    // Subscribe if race is starting within the next hour and at least 5 minutes away
                    if (timeUntilRace <= TimeSpan.FromHours(1) && timeUntilRace >= TimeSpan.FromMinutes(5))
                    {
                        // Try to find matching Betfair market
                        var marketId = await FindMarketId(venue, raceNumber, raceDate);
                        if (!string.IsNullOrEmpty(marketId))
                        {
                            races.Add(new RaceInfo
                            {
                                MarketId = marketId,
                                Venue = venue,
                                RaceNumber = raceNumber,
                                RaceTime = raceTime,
                                RaceDate = raceDate
                            });
                        }
                    }
                }
            }

            return races;
        }

        private async Task<string> FindMarketId(string venue, int raceNumber, string raceDate)
        {
            // Use the betfairmarket.sqlite database for HorseMarketBook
            var betfairConnectionString = "Data Source=/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite";
            using var connection = new SqliteConnection(betfairConnectionString);
            await connection.OpenAsync();

            // Try to match by venue and race number (date is embedded in EventName)
            var query = @"
                SELECT DISTINCT marketId 
                FROM HorseMarketBook 
                WHERE (EventName LIKE $venuePattern OR MarketName LIKE $venuePattern)
                AND (MarketName LIKE $racePattern OR MarketName LIKE $racePattern2)
                LIMIT 1";

            using var command = new SqliteCommand(query, connection);
            command.Parameters.AddWithValue("$venuePattern", $"%{venue}%");
            command.Parameters.AddWithValue("$racePattern", $"R{raceNumber}%");
            command.Parameters.AddWithValue("$racePattern2", $"Race {raceNumber}%");

            var result = await command.ExecuteScalarAsync();
            return result?.ToString();
        }

        private async Task SubscribeToMarket(string marketId, string venue, int raceNumber, DateTime raceTime)
        {
            try
            {
                using var scope = _serviceProvider.CreateScope();
                var streamApiService = scope.ServiceProvider.GetRequiredService<IStreamApiService>();

                await streamApiService.SubscribeToMarketAsync(marketId);
                _subscribedMarkets.Add(marketId);

                var timeUntilRace = raceTime - DateTime.UtcNow;
                _logger.LogInformation($"✅ Subscribed to {venue} R{raceNumber} (Market: {marketId}) - Race starts in {timeUntilRace.TotalMinutes:F1} minutes");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Failed to subscribe to market {marketId} for {venue} R{raceNumber}");
            }
        }

        private async Task CleanupOldSubscriptions()
        {
            var now = DateTime.UtcNow;
            var marketsToRemove = new List<string>();

            foreach (var marketId in _subscribedMarkets)
            {
                // Check if race has finished (assuming races last max 10 minutes)
                // Use the live_betting.sqlite database for race_times
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();

                var query = @"
                    SELECT race_time 
                    FROM race_times rt
                    JOIN HorseMarketBook hmb ON (hmb.EventName LIKE '%' || rt.venue || '%' OR hmb.MarketName LIKE '%' || rt.venue || '%')
                    WHERE hmb.marketId = $marketId
                    AND datetime(rt.race_time) < datetime('now', '-10 minutes')";

                using var command = new SqliteCommand(query, connection);
                command.Parameters.AddWithValue("$marketId", marketId);

                var raceTime = await command.ExecuteScalarAsync();
                if (raceTime != null && DateTime.TryParse(raceTime.ToString(), out var raceDateTime))
                {
                    if (now > raceDateTime.AddMinutes(10)) // Race finished 10+ minutes ago
                    {
                        marketsToRemove.Add(marketId);
                    }
                }
            }

            // Remove old subscriptions
            foreach (var marketId in marketsToRemove)
            {
                try
                {
                    using var scope = _serviceProvider.CreateScope();
                    var streamApiService = scope.ServiceProvider.GetRequiredService<IStreamApiService>();
                    await streamApiService.UnsubscribeFromMarketAsync(marketId);
                    _subscribedMarkets.Remove(marketId);
                    _logger.LogInformation($"Unsubscribed from finished race: {marketId}");
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, $"Failed to unsubscribe from market {marketId}");
                }
            }
        }

        public override async Task StopAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Automated Market Subscription Service stopping");
            _subscriptionTimer?.Dispose();
            await base.StopAsync(cancellationToken);
        }
    }

    public class RaceInfo
    {
        public string MarketId { get; set; }
        public string Venue { get; set; }
        public int RaceNumber { get; set; }
        public DateTime RaceTime { get; set; }
        public string RaceDate { get; set; }
    }
}
