using Betfair.Models.Simulation;
using Betfair.Services.RaceResults;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace Betfair.Services.Simulation
{
    /// <summary>
    /// Background service that automatically settles simulated bets by fetching race results
    /// </summary>
    public class AutomatedBetSettlementService : BackgroundService
    {
        private readonly IBettingSimulationService _simulationService;
        private readonly IRaceResultsService _raceResultsService;
        private readonly ILogger<AutomatedBetSettlementService> _logger;
        private readonly bool _isEnabled;
        private readonly int _settlementDelayMinutes;
        private readonly int _checkIntervalMinutes;

        public AutomatedBetSettlementService(
            IBettingSimulationService simulationService,
            IRaceResultsService raceResultsService,
            IConfiguration configuration,
            ILogger<AutomatedBetSettlementService> logger)
        {
            _simulationService = simulationService;
            _raceResultsService = raceResultsService;
            _logger = logger;
            _isEnabled = configuration.GetValue<bool>("RaceResults:AutoSettlementEnabled", true);
            _settlementDelayMinutes = configuration.GetValue<int>("RaceResults:SettlementDelayMinutes", 30);
            _checkIntervalMinutes = configuration.GetValue<int>("RaceResults:CheckIntervalMinutes", 15);
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            if (!_isEnabled)
            {
                _logger.LogInformation("🔕 Automated bet settlement is disabled");
                return;
            }

            _logger.LogInformation("🤖 Starting automated bet settlement service (check every {Interval} minutes)", _checkIntervalMinutes);

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await CheckAndSettlePendingBets();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "❌ Error in automated bet settlement");
                }

                // Wait for the next check interval
                await Task.Delay(TimeSpan.FromMinutes(_checkIntervalMinutes), stoppingToken);
            }
        }

        private async Task CheckAndSettlePendingBets()
        {
            _logger.LogDebug("🔍 Checking for bets to settle...");

            // Get pending bets that are old enough to settle
            var pendingBets = await _simulationService.GetPendingBetsAsync();
            var cutoffTime = DateTime.UtcNow.AddMinutes(-_settlementDelayMinutes);
            
            var betsToSettle = pendingBets
                .Where(b => b.EventTime < cutoffTime)
                .ToList();

            if (!betsToSettle.Any())
            {
                _logger.LogDebug("No bets ready for settlement");
                return;
            }

            _logger.LogInformation("🎯 Found {Count} bets ready for settlement", betsToSettle.Count);

            // Group by race (market)
            var raceGroups = betsToSettle
                .GroupBy(b => new { b.MarketId, b.EventName, b.EventTime.Date })
                .ToList();

            int totalSettled = 0;

            foreach (var raceGroup in raceGroups)
            {
                try
                {
                    var settledCount = await SettleRaceGroup(raceGroup);
                    totalSettled += settledCount;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error settling race group: {EventName}", raceGroup.Key.EventName);
                }
            }

            if (totalSettled > 0)
            {
                _logger.LogInformation("✅ Successfully settled {Count} bets", totalSettled);
            }
        }

        private async Task<int> SettleRaceGroup(IGrouping<dynamic, SimulatedBet> raceGroup)
        {
            var raceBets = raceGroup.ToList();
            var firstBet = raceBets.First();
            
            _logger.LogDebug("🏁 Attempting to settle race: {EventName} ({Count} bets)", 
                firstBet.EventName, raceBets.Count);

            try
            {
                // Try to find race results using multiple strategies
                RaceResult raceResult = null;

                // Strategy 1: Search by venue and race name
                var venue = ExtractVenue(firstBet.EventName);
                var raceName = ExtractRaceName(firstBet.MarketName);
                
                if (!string.IsNullOrEmpty(venue))
                {
                    var searchResults = await _raceResultsService.SearchRaceResultsAsync(
                        venue, raceName, firstBet.EventTime.Date);
                    
                    raceResult = searchResults.FirstOrDefault(r => 
                        Math.Abs((r.RaceTime - firstBet.EventTime).TotalMinutes) < 60);
                }

                // Strategy 2: If no result found, check recent finished races
                if (raceResult == null)
                {
                    var recentRaces = await _raceResultsService.GetRecentFinishedRacesAsync(48); // Last 48 hours
                    
                    raceResult = recentRaces.FirstOrDefault(r =>
                        r.Venue.Contains(venue ?? "", StringComparison.OrdinalIgnoreCase) &&
                        Math.Abs((r.RaceTime - firstBet.EventTime).TotalHours) < 2);
                }

                if (raceResult == null || raceResult.Status != RaceStatus.Finished)
                {
                    _logger.LogDebug("No race results found for {EventName} at {EventTime}", 
                        firstBet.EventName, firstBet.EventTime);
                    return 0;
                }

                _logger.LogInformation("📊 Found race result: {Venue} - {RaceName} with {Count} finishers", 
                    raceResult.Venue, raceResult.RaceName, raceResult.FinishingPositions.Count);

                // Map horse names to selection IDs
                var horseMapping = new Dictionary<string, long>();
                foreach (var bet in raceBets)
                {
                    horseMapping[bet.HorseName] = bet.SelectionId;
                }

                // Convert race result to selection results format
                var selectionResults = new Dictionary<long, int>();
                
                foreach (var position in raceResult.FinishingPositions)
                {
                    // Try exact match first
                    var matchingBet = raceBets.FirstOrDefault(b => 
                        string.Equals(b.HorseName, position.HorseName, StringComparison.OrdinalIgnoreCase));
                    
                    if (matchingBet == null)
                    {
                        // Try partial match (remove common suffixes/prefixes)
                        matchingBet = raceBets.FirstOrDefault(b => 
                            NormalizeHorseName(b.HorseName) == NormalizeHorseName(position.HorseName));
                    }

                    if (matchingBet != null)
                    {
                        selectionResults[matchingBet.SelectionId] = position.Position;
                        _logger.LogDebug("Matched horse: {BetName} -> {ResultName} (Position: {Position})",
                            matchingBet.HorseName, position.HorseName, position.Position);
                    }
                }

                if (selectionResults.Any())
                {
                    var settledCount = await _simulationService.SettleBetsForMarketAsync(
                        firstBet.MarketId, selectionResults);
                    
                    _logger.LogInformation("🏆 Settled {Count} bets for {EventName}", 
                        settledCount, firstBet.EventName);
                    
                    return settledCount;
                }
                else
                {
                    _logger.LogWarning("❓ Could not match any horses between bets and race results for {EventName}", 
                        firstBet.EventName);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error settling race: {EventName}", firstBet.EventName);
            }

            return 0;
        }

        private string ExtractVenue(string eventName)
        {
            if (string.IsNullOrEmpty(eventName))
                return "";

            // Common patterns: "Venue (Country) Date" or "Venue Date"
            var parts = eventName.Split(' ');
            if (parts.Length > 0)
            {
                var venue = parts[0];
                // Remove common suffixes
                venue = venue.Replace("(AUS)", "").Replace("(GB)", "").Replace("(IE)", "").Trim();
                return venue;
            }

            return "";
        }

        private string ExtractRaceName(string marketName)
        {
            if (string.IsNullOrEmpty(marketName))
                return "";

            // Common patterns: "Race Name | To Be Placed" or just "Race Name"
            var parts = marketName.Split('|');
            if (parts.Length > 0)
            {
                return parts[0].Trim();
            }

            return marketName;
        }

        private string NormalizeHorseName(string horseName)
        {
            if (string.IsNullOrEmpty(horseName))
                return "";

            return horseName
                .ToLowerInvariant()
                .Replace("'", "")
                .Replace("-", " ")
                .Replace("  ", " ")
                .Trim();
        }
    }
}
