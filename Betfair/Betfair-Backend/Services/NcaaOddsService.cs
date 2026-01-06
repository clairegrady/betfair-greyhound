using System.Text.Json;
using System.Text.Json.Serialization;
using Betfair.Models.NcaaBasketball;

namespace Betfair.Services;

public interface INcaaOddsService
{
    Task<Dictionary<string, OddsData>> GetTodaysOddsAsync();
    Task<OddsData?> GetOddsForGameAsync(string homeTeam, string awayTeam);
    Task<List<OddsApiGame>> GetUpcomingGamesAsync();
}

public class NcaaOddsService : INcaaOddsService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<NcaaOddsService> _logger;
    private readonly IConfiguration _configuration;

    public NcaaOddsService(HttpClient httpClient, ILogger<NcaaOddsService> logger, IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _configuration = configuration;
    }

    public async Task<Dictionary<string, OddsData>> GetTodaysOddsAsync()
    {
        var oddsMap = new Dictionary<string, OddsData>();

        try
        {
            // Check if we have The Odds API key configured
            var apiKey = _configuration["OddsApi:ApiKey"];
            
            if (string.IsNullOrEmpty(apiKey))
            {
                _logger.LogWarning("Odds API key not configured. Returning empty odds.");
                return oddsMap;
            }

            // Fetch odds from The Odds API
            var url = $"https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/?apiKey={apiKey}&regions=us&markets=h2h";
            
            var response = await _httpClient.GetAsync(url);
            
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning($"Failed to fetch odds: {response.StatusCode}");
                return oddsMap;
            }

            var json = await response.Content.ReadAsStringAsync();
            var games = JsonSerializer.Deserialize<List<OddsApiGame>>(json);

            if (games == null)
            {
                return oddsMap;
            }

            // Parse odds
            foreach (var game in games)
            {
                if (game.Bookmakers == null || game.Bookmakers.Count == 0)
                    continue;

                // Use first bookmaker (typically best odds or most reliable)
                var bookmaker = game.Bookmakers[0];
                var h2hMarket = bookmaker.Markets?.FirstOrDefault(m => m.Key == "h2h");
                
                if (h2hMarket?.Outcomes == null || h2hMarket.Outcomes.Count < 2)
                    continue;

                // Find home and away odds
                var homeOutcome = h2hMarket.Outcomes.FirstOrDefault(o => o.Name == game.HomeTeam);
                var awayOutcome = h2hMarket.Outcomes.FirstOrDefault(o => o.Name == game.AwayTeam);

                if (homeOutcome != null && awayOutcome != null)
                {
                    var key = $"{game.AwayTeam}@{game.HomeTeam}";
                    oddsMap[key] = new OddsData
                    {
                        HomeTeam = game.HomeTeam,
                        AwayTeam = game.AwayTeam,
                        HomeOdds = homeOutcome.Price,
                        AwayOdds = awayOutcome.Price,
                        Bookmaker = bookmaker.Title,
                        LastUpdate = game.CommenceTime
                    };
                }
            }

            _logger.LogInformation($"Fetched odds for {oddsMap.Count} games");
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error fetching odds: {ex.Message}");
        }

        return oddsMap;
    }

    public async Task<OddsData?> GetOddsForGameAsync(string homeTeam, string awayTeam)
    {
        var allOdds = await GetTodaysOddsAsync();
        var key = $"{awayTeam}@{homeTeam}";
        
        return allOdds.ContainsKey(key) ? allOdds[key] : null;
    }

    public async Task<List<OddsApiGame>> GetUpcomingGamesAsync()
    {
        var games = new List<OddsApiGame>();

        try
        {
            _logger.LogInformation("🎯 GetUpcomingGamesAsync called");
            
            // Check if we have The Odds API key configured
            var apiKey = _configuration["OddsApi:ApiKey"];
            
            if (string.IsNullOrEmpty(apiKey))
            {
                _logger.LogWarning("Odds API key not configured. Returning empty games list.");
                return games;
            }

            _logger.LogInformation("📡 Fetching from The Odds API...");
            
            // Fetch odds from The Odds API (gets next few days of games)
            var url = $"https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/?apiKey={apiKey}&regions=us&markets=h2h";
            
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30)); // 30-second timeout
            var response = await _httpClient.GetAsync(url, cts.Token);
            
            _logger.LogInformation($"📥 API Response: {response.StatusCode}");
            
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning($"Failed to fetch upcoming games: {response.StatusCode}");
                return games;
            }

            var json = await response.Content.ReadAsStringAsync();
            _logger.LogInformation($"📄 JSON length: {json.Length} characters");
            
            var apiGames = JsonSerializer.Deserialize<List<OddsApiGame>>(json);

            if (apiGames != null)
            {
                games = apiGames;
                _logger.LogInformation($"✅ Fetched {games.Count} upcoming NCAA Basketball games");
            }
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError($"⏱️ Timeout fetching upcoming games: {ex.Message}");
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Error fetching upcoming games: {ex.Message}");
            _logger.LogError($"   Exception type: {ex.GetType().Name}");
        }

        return games;
    }
}

// Models for The Odds API
public class OddsApiGame
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;
    
    [JsonPropertyName("home_team")]
    public string HomeTeam { get; set; } = string.Empty;
    
    [JsonPropertyName("away_team")]
    public string AwayTeam { get; set; } = string.Empty;
    
    [JsonPropertyName("commence_time")]
    public DateTime CommenceTime { get; set; }
    
    [JsonPropertyName("bookmakers")]
    public List<Bookmaker> Bookmakers { get; set; } = new();
}

public class Bookmaker
{
    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;
    
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;
    
    [JsonPropertyName("last_update")]
    public DateTime LastUpdate { get; set; }
    
    [JsonPropertyName("markets")]
    public List<Market> Markets { get; set; } = new();
}

public class Market
{
    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;
    
    [JsonPropertyName("outcomes")]
    public List<Outcome> Outcomes { get; set; } = new();
}

public class Outcome
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("price")]
    public double Price { get; set; }
}

public class OddsData
{
    public string HomeTeam { get; set; } = string.Empty;
    public string AwayTeam { get; set; } = string.Empty;
    public double HomeOdds { get; set; }
    public double AwayOdds { get; set; }
    public string Bookmaker { get; set; } = string.Empty;
    public DateTime LastUpdate { get; set; }
}

