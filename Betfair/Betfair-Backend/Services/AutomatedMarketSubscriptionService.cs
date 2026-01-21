using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Npgsql;
using Betfair.AutomatedServices;

namespace Betfair.Services
{
    public class AutomatedMarketSubscriptionService : BackgroundService
    {
        private readonly ILogger<AutomatedMarketSubscriptionService> _logger;
        private readonly IServiceProvider _serviceProvider;
        private readonly string _connectionString;
        private readonly string _betfairConnectionString;
        private readonly HashSet<string> _subscribedMarkets = new();
        private Timer _subscriptionTimer;

        public AutomatedMarketSubscriptionService(
            ILogger<AutomatedMarketSubscriptionService> logger,
            IServiceProvider serviceProvider,
            Microsoft.Extensions.Configuration.IConfiguration configuration)
        {
            _logger = logger;
            _serviceProvider = serviceProvider;
            // Use the RacesDb for race times and DefaultDb for market data
            _connectionString = configuration.GetConnectionString("RacesDb") 
                ?? throw new InvalidOperationException("RacesDb connection string not found");
            _betfairConnectionString = configuration.GetConnectionString("DefaultDb") 
                ?? throw new InvalidOperationException("DefaultDb connection string not found");
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
            var races = new List<RaceInfo>();
            var now = DateTime.UtcNow;
            var subscriptionWindow = TimeSpan.FromMinutes(15); // Subscribe 15 minutes before race

            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get races from BOTH horse_race_times AND greyhound_race_times that are starting soon
            var raceTimesQuery = @"
                SELECT venue, race_number, race_time, race_date, 'horse' as race_type
                FROM horse_race_times 
                WHERE race_date::date >= CURRENT_DATE
                AND race_time BETWEEN NOW() AND NOW() + INTERVAL '1 hour'
                UNION ALL
                SELECT venue, race_number, race_time, race_date, 'greyhound' as race_type
                FROM greyhound_race_times 
                WHERE race_date::date >= CURRENT_DATE
                AND race_time BETWEEN NOW() AND NOW() + INTERVAL '1 hour'
                ORDER BY race_time";

            using var raceTimesCommand = new NpgsqlCommand(raceTimesQuery, connection);
            using var raceTimesReader = await raceTimesCommand.ExecuteReaderAsync();

            while (await raceTimesReader.ReadAsync())
            {
                var venue = raceTimesReader.GetString(0); // venue column
                var raceNumber = raceTimesReader.GetInt32(1); // race_number column
                var raceTimeStr = raceTimesReader.GetString(2); // race_time column (TEXT type)
                var raceDate = raceTimesReader.GetString(3); // race_date column
                var raceType = raceTimesReader.GetString(4); // race_type column
                
                // Parse the race time string (format: HH:MM)
                if (!DateTime.TryParse($"{raceDate} {raceTimeStr}", out DateTime raceTime))
                {
                    continue;
                }

                var timeUntilRace = raceTime - now;
                
                // Subscribe if race is starting within the next hour and at least 5 minutes away
                if (timeUntilRace <= TimeSpan.FromHours(1) && timeUntilRace >= TimeSpan.FromMinutes(5))
                {
                    // Try to find matching Betfair market
                    var marketId = await FindMarketId(venue, raceNumber, raceDate, raceType);
                    if (!string.IsNullOrEmpty(marketId))
                    {
                        races.Add(new RaceInfo
                        {
                            MarketId = marketId,
                            Venue = venue,
                            RaceNumber = raceNumber,
                            RaceTime = raceTime,
                            RaceDate = raceDate,
                            RaceType = raceType
                        });
                    }
                }
            }

            _logger.LogInformation($"Found {races.Count} upcoming races to subscribe to ({races.Count(r => r.RaceType == "horse")} horses, {races.Count(r => r.RaceType == "greyhound")} greyhounds)");
            return races;
        }

        private async Task<string> FindMarketId(string venue, int raceNumber, string raceDate, string raceType)
        {
            // Use the betfairmarket database
            using var connection = new NpgsqlConnection(_betfairConnectionString);
            await connection.OpenAsync();

            // Choose the correct table based on race type
            var tableName = raceType == "horse" ? "horsemarketbook" : "greyhoundmarketbook";
            
            // Try to match by venue and race number (date is embedded in EventName)
            var query = $@"
                SELECT DISTINCT marketid 
                FROM {tableName}
                WHERE (eventname ILIKE @venuePattern OR marketname ILIKE @venuePattern)
                AND (marketname ILIKE @racePattern OR marketname ILIKE @racePattern2)
                LIMIT 1";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@venuePattern", $"%{venue}%");
            command.Parameters.AddWithValue("@racePattern", $"R{raceNumber}%");
            command.Parameters.AddWithValue("@racePattern2", $"Race {raceNumber}%");

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
                using var racesConn = new NpgsqlConnection(_connectionString);
                await racesConn.OpenAsync();

                // Check both horse and greyhound race times
                var query = @"
                    SELECT race_time::timestamp 
                    FROM horse_race_times
                    WHERE (race_date || ' ' || race_time)::timestamp < NOW() - INTERVAL '10 minutes'
                    AND venue IN (
                        SELECT DISTINCT substring(eventname from 1 for position('(' in eventname) - 1)
                        FROM horsemarketbook 
                        WHERE marketid = @marketId
                    )
                    UNION ALL
                    SELECT race_time::timestamp
                    FROM greyhound_race_times
                    WHERE (race_date || ' ' || race_time)::timestamp < NOW() - INTERVAL '10 minutes'
                    AND venue IN (
                        SELECT DISTINCT substring(eventname from 1 for position('(' in eventname) - 1)
                        FROM greyhoundmarketbook
                        WHERE marketid = @marketId
                    )
                    LIMIT 1";

                using var command = new NpgsqlCommand(query, racesConn);
                command.Parameters.AddWithValue("@marketId", marketId);

                var result = await command.ExecuteScalarAsync();
                if (result != null)
                {
                    marketsToRemove.Add(marketId);
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
        public string RaceType { get; set; } // "horse" or "greyhound"
    }
}
