using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Betfair.Services.RaceResults
{
    /// <summary>
    /// Composite service that tries multiple race result providers in order
    /// This ensures high reliability by falling back to alternative sources
    /// </summary>
    public class CompositeRaceResultsService : IRaceResultsService
    {
        private readonly List<IRaceResultsProvider> _providers;
        private readonly ILogger<CompositeRaceResultsService> _logger;

        public CompositeRaceResultsService(
            IEnumerable<IRaceResultsProvider> providers,
            ILogger<CompositeRaceResultsService> logger)
        {
            _providers = providers.OrderBy(p => p.Priority).ToList();
            _logger = logger;
        }

        public async Task<List<RaceResult>> GetRaceResultsAsync(DateTime raceDate, string country = "AU")
        {
            _logger.LogInformation("🔍 Fetching race results for {Date} in {Country}", raceDate.ToString("yyyy-MM-dd"), country);

            var allResults = new List<RaceResult>();

            foreach (var provider in _providers)
            {
                try
                {
                    _logger.LogDebug("Trying provider: {Provider}", provider.GetType().Name);
                    var results = await provider.GetRaceResultsAsync(raceDate, country);
                    
                    if (results.Any())
                    {
                        allResults.AddRange(results);
                        _logger.LogInformation("✅ {Provider} returned {Count} race results", 
                            provider.GetType().Name, results.Count);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "⚠️ {Provider} failed to fetch results: {Message}", 
                        provider.GetType().Name, ex.Message);
                }
            }

            // Remove duplicates based on venue and race name
            var uniqueResults = allResults
                .GroupBy(r => new { r.Venue, r.RaceName, r.RaceTime.Date })
                .Select(g => g.OrderBy(r => GetProviderPriority(r.ResultSource)).First())
                .ToList();

            _logger.LogInformation("📊 Found {Total} total results, {Unique} unique races", 
                allResults.Count, uniqueResults.Count);

            return uniqueResults;
        }

        public async Task<RaceResult> GetRaceResultByIdAsync(string externalRaceId)
        {
            foreach (var provider in _providers)
            {
                try
                {
                    var result = await provider.GetRaceResultByIdAsync(externalRaceId);
                    if (result != null)
                    {
                        _logger.LogInformation("✅ {Provider} found result for race ID: {RaceId}", 
                            provider.GetType().Name, externalRaceId);
                        return result;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "⚠️ {Provider} failed to fetch race {RaceId}: {Message}", 
                        provider.GetType().Name, externalRaceId, ex.Message);
                }
            }

            _logger.LogWarning("❌ No provider found result for race ID: {RaceId}", externalRaceId);
            return null;
        }

        public async Task<List<RaceResult>> SearchRaceResultsAsync(string venue, string raceName, DateTime raceDate)
        {
            _logger.LogInformation("🔍 Searching for race: {Venue} - {RaceName} on {Date}", 
                venue, raceName, raceDate.ToString("yyyy-MM-dd"));

            var allResults = new List<RaceResult>();

            foreach (var provider in _providers)
            {
                try
                {
                    var results = await provider.SearchRaceResultsAsync(venue, raceName, raceDate);
                    if (results.Any())
                    {
                        allResults.AddRange(results);
                        _logger.LogInformation("✅ {Provider} found {Count} matching races", 
                            provider.GetType().Name, results.Count);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "⚠️ {Provider} failed to search: {Message}", 
                        provider.GetType().Name, ex.Message);
                }
            }

            return allResults.OrderBy(r => GetProviderPriority(r.ResultSource)).ToList();
        }

        public async Task<List<RaceResult>> GetRecentFinishedRacesAsync(int hoursBack = 4)
        {
            _logger.LogInformation("🔍 Fetching races finished in the last {Hours} hours", hoursBack);

            var allResults = new List<RaceResult>();

            foreach (var provider in _providers)
            {
                try
                {
                    var results = await provider.GetRecentFinishedRacesAsync(hoursBack);
                    if (results.Any())
                    {
                        allResults.AddRange(results);
                        _logger.LogInformation("✅ {Provider} found {Count} recent finished races", 
                            provider.GetType().Name, results.Count);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "⚠️ {Provider} failed to fetch recent races: {Message}", 
                        provider.GetType().Name, ex.Message);
                }
            }

            var uniqueResults = allResults
                .GroupBy(r => new { r.Venue, r.RaceName, r.RaceTime })
                .Select(g => g.OrderBy(r => GetProviderPriority(r.ResultSource)).First())
                .OrderByDescending(r => r.RaceTime)
                .ToList();

            return uniqueResults;
        }

        public async Task<RaceResult> CheckRaceStatusAsync(string venue, string raceName, DateTime eventTime)
        {
            foreach (var provider in _providers)
            {
                try
                {
                    var result = await provider.CheckRaceStatusAsync(venue, raceName, eventTime);
                    if (result?.Status == RaceStatus.Finished)
                    {
                        _logger.LogInformation("✅ {Provider} confirmed race finished: {Venue} - {RaceName}", 
                            provider.GetType().Name, venue, raceName);
                        return result;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "⚠️ {Provider} failed to check race status: {Message}", 
                        provider.GetType().Name, ex.Message);
                }
            }

            return null;
        }

        private int GetProviderPriority(string resultSource)
        {
            var provider = _providers.FirstOrDefault(p => p.GetType().Name.Contains(resultSource));
            return provider?.Priority ?? 999;
        }
    }

    /// <summary>
    /// Base interface for race result providers
    /// </summary>
    public interface IRaceResultsProvider : IRaceResultsService
    {
        /// <summary>
        /// Priority of this provider (lower = higher priority)
        /// </summary>
        int Priority { get; }

        /// <summary>
        /// Name of this provider
        /// </summary>
        string ProviderName { get; }

        /// <summary>
        /// Countries/regions this provider supports
        /// </summary>
        List<string> SupportedCountries { get; }

        /// <summary>
        /// Check if this provider is available
        /// </summary>
        Task<bool> IsAvailableAsync();
    }
}
