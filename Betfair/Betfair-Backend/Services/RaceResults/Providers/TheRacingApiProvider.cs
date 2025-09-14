using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace Betfair.Services.RaceResults.Providers
{
    /// <summary>
    /// Race results provider using The Racing API (UK, Ireland, USA)
    /// https://www.theracingapi.com/
    /// </summary>
    public class TheRacingApiProvider : IRaceResultsProvider
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<TheRacingApiProvider> _logger;
        private readonly string _apiKey;
        private readonly string _baseUrl = "https://api.theracingapi.com/v1";

        public int Priority => 1; // High priority for quality data
        public string ProviderName => "The Racing API";
        public List<string> SupportedCountries => new List<string> { "UK", "IE", "US" };

        public TheRacingApiProvider(
            HttpClient httpClient,
            IConfiguration configuration,
            ILogger<TheRacingApiProvider> logger)
        {
            _httpClient = httpClient;
            _logger = logger;
            _apiKey = configuration["RaceResults:TheRacingApi:ApiKey"];
            
            if (string.IsNullOrEmpty(_apiKey))
            {
                _logger.LogWarning("⚠️ The Racing API key not configured");
            }
        }

        public async Task<bool> IsAvailableAsync()
        {
            if (string.IsNullOrEmpty(_apiKey))
                return false;

            try
            {
                var response = await _httpClient.GetAsync($"{_baseUrl}/regions?api_key={_apiKey}");
                return response.IsSuccessStatusCode;
            }
            catch
            {
                return false;
            }
        }

        public async Task<List<RaceResult>> GetRaceResultsAsync(DateTime raceDate, string country = "AU")
        {
            if (!SupportedCountries.Contains(country))
            {
                _logger.LogDebug("Country {Country} not supported by {Provider}", country, ProviderName);
                return new List<RaceResult>();
            }

            if (string.IsNullOrEmpty(_apiKey))
            {
                _logger.LogWarning("API key not configured for {Provider}", ProviderName);
                return new List<RaceResult>();
            }

            try
            {
                // Map country codes
                var region = country switch
                {
                    "UK" => "gb",
                    "IE" => "ie", 
                    "US" => "us",
                    _ => "gb" // Default to GB
                };

                var dateStr = raceDate.ToString("yyyy-MM-dd");
                var url = $"{_baseUrl}/results/{region}/{dateStr}?api_key={_apiKey}";

                _logger.LogDebug("Fetching results from: {Url}", url);
                var response = await _httpClient.GetAsync(url);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning("API returned {StatusCode} for date {Date}", response.StatusCode, dateStr);
                    return new List<RaceResult>();
                }

                var jsonContent = await response.Content.ReadAsStringAsync();
                var apiResponse = JsonSerializer.Deserialize<TheRacingApiResponse>(jsonContent);

                return ConvertToRaceResults(apiResponse);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching results from {Provider} for {Date}", ProviderName, raceDate);
                return new List<RaceResult>();
            }
        }

        public async Task<RaceResult> GetRaceResultByIdAsync(string externalRaceId)
        {
            if (string.IsNullOrEmpty(_apiKey))
                return null;

            try
            {
                var url = $"{_baseUrl}/results/race/{externalRaceId}?api_key={_apiKey}";
                var response = await _httpClient.GetAsync(url);
                
                if (!response.IsSuccessStatusCode)
                    return null;

                var jsonContent = await response.Content.ReadAsStringAsync();
                var raceData = JsonSerializer.Deserialize<TheRacingApiRace>(jsonContent);

                return ConvertToRaceResult(raceData);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching race {RaceId} from {Provider}", externalRaceId, ProviderName);
                return null;
            }
        }

        public async Task<List<RaceResult>> SearchRaceResultsAsync(string venue, string raceName, DateTime raceDate)
        {
            // The Racing API doesn't have a direct search endpoint, so we fetch all results for the date
            // and filter client-side
            var allResults = await GetRaceResultsAsync(raceDate);
            
            return allResults.Where(r => 
                r.Venue.Contains(venue, StringComparison.OrdinalIgnoreCase) &&
                r.RaceName.Contains(raceName, StringComparison.OrdinalIgnoreCase)
            ).ToList();
        }

        public async Task<List<RaceResult>> GetRecentFinishedRacesAsync(int hoursBack = 4)
        {
            var allResults = new List<RaceResult>();
            var endDate = DateTime.UtcNow;
            var startDate = endDate.AddHours(-hoursBack);

            // Check last few days to cover the time range
            for (var date = startDate.Date; date <= endDate.Date; date = date.AddDays(1))
            {
                var dayResults = await GetRaceResultsAsync(date);
                var recentResults = dayResults.Where(r => 
                    r.RaceTime >= startDate && 
                    r.RaceTime <= endDate &&
                    r.Status == RaceStatus.Finished
                ).ToList();
                
                allResults.AddRange(recentResults);
            }

            return allResults.OrderByDescending(r => r.RaceTime).ToList();
        }

        public async Task<RaceResult> CheckRaceStatusAsync(string venue, string raceName, DateTime eventTime)
        {
            var results = await SearchRaceResultsAsync(venue, raceName, eventTime.Date);
            return results.FirstOrDefault(r => Math.Abs((r.RaceTime - eventTime).TotalMinutes) < 30);
        }

        private List<RaceResult> ConvertToRaceResults(TheRacingApiResponse apiResponse)
        {
            var results = new List<RaceResult>();

            if (apiResponse?.Races == null)
                return results;

            foreach (var race in apiResponse.Races)
            {
                var result = ConvertToRaceResult(race);
                if (result != null)
                    results.Add(result);
            }

            return results;
        }

        private RaceResult ConvertToRaceResult(TheRacingApiRace race)
        {
            if (race == null)
                return null;

            var result = new RaceResult
            {
                ExternalRaceId = race.Id?.ToString(),
                Venue = race.Course ?? "",
                RaceName = race.Title ?? "",
                RaceTime = ParseDateTime(race.OffTime),
                ResultTime = ParseDateTime(race.ResultTime),
                Status = race.Status == "result" ? RaceStatus.Finished : RaceStatus.Unknown,
                ResultSource = ProviderName,
                FinishingPositions = new List<HorseFinishingPosition>()
            };

            if (race.Runners != null)
            {
                foreach (var runner in race.Runners)
                {
                    if (runner.FinishPosition.HasValue && runner.FinishPosition > 0)
                    {
                        result.FinishingPositions.Add(new HorseFinishingPosition
                        {
                            HorseName = runner.Name ?? "",
                            Position = runner.FinishPosition.Value,
                            Jockey = runner.Jockey ?? "",
                            StartingPrice = runner.StartingPrice,
                            Comments = runner.Comments ?? "",
                            IsNonRunner = runner.IsNonRunner
                        });
                    }
                }
            }

            return result;
        }

        private DateTime ParseDateTime(string dateTimeStr)
        {
            if (string.IsNullOrEmpty(dateTimeStr))
                return DateTime.MinValue;

            if (DateTime.TryParse(dateTimeStr, out DateTime result))
                return result;

            return DateTime.MinValue;
        }

        #region API Response Models

        private class TheRacingApiResponse
        {
            public List<TheRacingApiRace> Races { get; set; }
        }

        private class TheRacingApiRace
        {
            public int? Id { get; set; }
            public string Title { get; set; }
            public string Course { get; set; }
            public string OffTime { get; set; }
            public string ResultTime { get; set; }
            public string Status { get; set; }
            public List<TheRacingApiRunner> Runners { get; set; }
        }

        private class TheRacingApiRunner
        {
            public string Name { get; set; }
            public string Jockey { get; set; }
            public int? FinishPosition { get; set; }
            public decimal? StartingPrice { get; set; }
            public string Comments { get; set; }
            public bool IsNonRunner { get; set; }
        }

        #endregion
    }
}
