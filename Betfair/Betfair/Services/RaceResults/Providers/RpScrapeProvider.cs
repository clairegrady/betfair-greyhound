using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Globalization;

namespace Betfair.Services.RaceResults.Providers
{
    /// <summary>
    /// Race results provider using rpscrape for Australian and international racing data
    /// Uses your existing rpscrape installation to fetch recent race results
    /// </summary>
    public class RpScrapeProvider : IRaceResultsProvider
    {
        private readonly ILogger<RpScrapeProvider> _logger;
        private readonly string _rpScrapePath;
        private readonly string _tempOutputPath;

        public int Priority => 2; // Good priority for Australian data
        public string ProviderName => "RPScrape";
        public List<string> SupportedCountries => new List<string> { "AU", "GB", "IE", "US", "FR", "DE" };

        public RpScrapeProvider(
            IConfiguration configuration,
            ILogger<RpScrapeProvider> logger)
        {
            _logger = logger;
            _rpScrapePath = configuration["RaceResults:RPScrape:ScriptPath"] ?? "/Users/clairegrady/rpscrape/scripts";
            _tempOutputPath = configuration["RaceResults:RPScrape:TempPath"] ?? Path.GetTempPath();
            
            _logger.LogInformation("📊 RPScrape provider initialized with path: {Path}", _rpScrapePath);
        }

        public async Task<bool> IsAvailableAsync()
        {
            try
            {
                var rpScrapeScript = Path.Combine(_rpScrapePath, "rpscrape.py");
                return File.Exists(rpScrapeScript);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error checking RPScrape availability");
                return false;
            }
        }

        public async Task<List<RaceResult>> GetRaceResultsAsync(DateTime raceDate, string country = "AU")
        {
            if (!await IsAvailableAsync())
            {
                _logger.LogWarning("RPScrape not available at path: {Path}", _rpScrapePath);
                return new List<RaceResult>();
            }

            try
            {
                var regionCode = GetRegionCode(country);
                if (string.IsNullOrEmpty(regionCode))
                {
                    _logger.LogDebug("Country {Country} not supported by RPScrape", country);
                    return new List<RaceResult>();
                }

                var results = new List<RaceResult>();
                
                // Scrape both flat and jumps for the date
                var flatResults = await ScrapeByDate(raceDate, regionCode, "flat");
                var jumpsResults = await ScrapeByDate(raceDate, regionCode, "jumps");
                
                results.AddRange(flatResults);
                results.AddRange(jumpsResults);

                _logger.LogInformation("✅ RPScrape found {Count} races for {Date} in {Country}", 
                    results.Count, raceDate.ToString("yyyy-MM-dd"), country);

                return results;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching results from RPScrape for {Date}", raceDate);
                return new List<RaceResult>();
            }
        }

        public async Task<RaceResult> GetRaceResultByIdAsync(string externalRaceId)
        {
            // RPScrape doesn't support direct race ID lookup
            _logger.LogDebug("RPScrape doesn't support race ID lookup for: {RaceId}", externalRaceId);
            return null;
        }

        public async Task<List<RaceResult>> SearchRaceResultsAsync(string venue, string raceName, DateTime raceDate)
        {
            // Get all results for the date and filter by venue
            var allResults = await GetRaceResultsAsync(raceDate, "AU"); // Default to AU
            
            return allResults.Where(r => 
                r.Venue.Contains(venue, StringComparison.OrdinalIgnoreCase)
            ).ToList();
        }

        public async Task<List<RaceResult>> GetRecentFinishedRacesAsync(int hoursBack = 4)
        {
            var allResults = new List<RaceResult>();
            var endDate = DateTime.Now;
            var startDate = endDate.AddHours(-hoursBack);

            // Check the last 2 days to cover the time range
            for (var date = startDate.Date; date <= endDate.Date; date = date.AddDays(1))
            {
                var dayResults = await GetRaceResultsAsync(date, "AU");
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

        private async Task<List<RaceResult>> ScrapeByDate(DateTime date, string regionCode, string raceType)
        {
            try
            {
                var dateStr = date.ToString("yyyy/MM/dd");
                var outputFile = Path.Combine(_tempOutputPath, $"rpscrape_{regionCode}_{date:yyyyMMdd}_{raceType}.csv");
                
                // Clean up any existing output file
                if (File.Exists(outputFile))
                    File.Delete(outputFile);

                var rpScrapeScript = Path.Combine(_rpScrapePath, "rpscrape.py");
                var workingDir = _rpScrapePath;

                // Build the command: python3 rpscrape.py -d 2024/08/20 -r au
                var arguments = $"-d {dateStr} -r {regionCode}";
                
                _logger.LogDebug("Running RPScrape: python3 {Script} {Args}", rpScrapeScript, arguments);

                var processInfo = new ProcessStartInfo
                {
                    FileName = "python3",
                    Arguments = $"\"{rpScrapeScript}\" {arguments}",
                    WorkingDirectory = workingDir,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(processInfo);
                if (process == null)
                {
                    _logger.LogError("Failed to start RPScrape process");
                    return new List<RaceResult>();
                }

                var output = await process.StandardOutput.ReadToEndAsync();
                var error = await process.StandardError.ReadToEndAsync();
                
                await process.WaitForExitAsync();

                if (process.ExitCode != 0)
                {
                    _logger.LogWarning("RPScrape exited with code {ExitCode}. Error: {Error}", process.ExitCode, error);
                }

                _logger.LogDebug("RPScrape output: {Output}", output);

                // Look for the generated CSV file
                var csvFiles = Directory.GetFiles(workingDir, "*.csv")
                    .Where(f => f.Contains(date.ToString("yyyy")) && f.Contains(regionCode))
                    .OrderByDescending(f => File.GetCreationTime(f))
                    .ToList();

                if (!csvFiles.Any())
                {
                    _logger.LogDebug("No CSV files found for {Date} {Region} {Type}", dateStr, regionCode, raceType);
                    return new List<RaceResult>();
                }

                var latestFile = csvFiles.First();
                _logger.LogDebug("Processing CSV file: {File}", latestFile);

                var results = await ParseCsvResults(latestFile, date);
                
                // Clean up the CSV file
                try { File.Delete(latestFile); } catch { }

                return results;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error scraping data for {Date} {Region} {Type}", date, regionCode, raceType);
                return new List<RaceResult>();
            }
        }

        private async Task<List<RaceResult>> ParseCsvResults(string csvFilePath, DateTime raceDate)
        {
            var results = new List<RaceResult>();

            try
            {
                var lines = await File.ReadAllLinesAsync(csvFilePath);
                if (lines.Length < 2) // Need header + at least one data row
                    return results;

                var header = lines[0].Split(',');
                var races = new Dictionary<string, RaceResult>();

                for (int i = 1; i < lines.Length; i++)
                {
                    try
                    {
                        var values = ParseCsvLine(lines[i]);
                        if (values.Length < header.Length)
                            continue;

                        var raceData = new Dictionary<string, string>();
                        for (int j = 0; j < Math.Min(header.Length, values.Length); j++)
                        {
                            raceData[header[j].Trim()] = values[j].Trim();
                        }

                        var raceKey = GetRaceKey(raceData);
                        if (string.IsNullOrEmpty(raceKey))
                            continue;

                        if (!races.ContainsKey(raceKey))
                        {
                            races[raceKey] = new RaceResult
                            {
                                ExternalRaceId = raceKey,
                                Venue = GetValue(raceData, "course") ?? "",
                                RaceName = GetValue(raceData, "race_title") ?? "",
                                RaceTime = ParseRaceTime(raceData, raceDate),
                                Status = RaceStatus.Finished, // RPScrape only gets historical results
                                ResultSource = ProviderName,
                                FinishingPositions = new List<HorseFinishingPosition>()
                            };
                        }

                        var race = races[raceKey];
                        var position = ParsePosition(GetValue(raceData, "position") ?? "");
                        
                        if (position > 0)
                        {
                            race.FinishingPositions.Add(new HorseFinishingPosition
                            {
                                HorseName = GetValue(raceData, "horse_name") ?? "",
                                Position = position,
                                Jockey = GetValue(raceData, "jockey_name") ?? "",
                                StartingPrice = ParseDecimal(GetValue(raceData, "starting_price")),
                                Comments = GetValue(raceData, "comment") ?? ""
                            });
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogDebug(ex, "Error parsing CSV line {LineNumber}: {Line}", i, lines[i]);
                    }
                }

                results.AddRange(races.Values);
                _logger.LogDebug("Parsed {RaceCount} races with {TotalHorses} horses from CSV", 
                    races.Count, results.Sum(r => r.FinishingPositions.Count));
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error parsing CSV file: {File}", csvFilePath);
            }

            return results;
        }

        private string[] ParseCsvLine(string line)
        {
            // Simple CSV parser - handles quoted fields
            var result = new List<string>();
            var current = "";
            var inQuotes = false;

            for (int i = 0; i < line.Length; i++)
            {
                var c = line[i];
                
                if (c == '"')
                {
                    inQuotes = !inQuotes;
                }
                else if (c == ',' && !inQuotes)
                {
                    result.Add(current);
                    current = "";
                }
                else
                {
                    current += c;
                }
            }
            
            result.Add(current);
            return result.ToArray();
        }

        private string GetRaceKey(Dictionary<string, string> raceData)
        {
            var course = GetValue(raceData, "course") ?? "";
            var date = GetValue(raceData, "date") ?? "";
            var time = GetValue(raceData, "time") ?? "";
            
            return $"{course}_{date}_{time}".Replace(" ", "_").Replace("/", "_");
        }

        private string GetValue(Dictionary<string, string> data, string key)
        {
            return data.TryGetValue(key, out string value) ? value?.Trim('"') : null;
        }

        private DateTime ParseRaceTime(Dictionary<string, string> raceData, DateTime fallbackDate)
        {
            var dateStr = GetValue(raceData, "date");
            var timeStr = GetValue(raceData, "time");

            if (DateTime.TryParseExact(dateStr, "dd/MM/yyyy", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime raceDate))
            {
                if (TimeSpan.TryParse(timeStr, out TimeSpan raceTime))
                {
                    return raceDate.Add(raceTime);
                }
                return raceDate;
            }

            return fallbackDate;
        }

        private int ParsePosition(string positionStr)
        {
            if (string.IsNullOrEmpty(positionStr))
                return 0;

            // Handle positions like "1st", "2nd", "3rd", "4th" or just "1", "2", etc.
            var cleanPos = positionStr.ToLower()
                .Replace("st", "")
                .Replace("nd", "")
                .Replace("rd", "")
                .Replace("th", "");

            return int.TryParse(cleanPos, out int position) ? position : 0;
        }

        private decimal? ParseDecimal(string value)
        {
            if (string.IsNullOrEmpty(value))
                return null;

            return decimal.TryParse(value, out decimal result) ? result : null;
        }

        private string GetRegionCode(string country)
        {
            return country.ToUpper() switch
            {
                "AU" => "aus",
                "GB" => "gb", 
                "UK" => "gb",
                "IE" => "ire",
                "US" => "usa",
                "FR" => "fr",
                "DE" => "ger",
                _ => null
            };
        }
    }
}
