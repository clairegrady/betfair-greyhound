using System.Text;
using System.Text.Json;
using Betfair.Data;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services;
public class MarketApiService : IMarketApiService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly MarketProfitAndLossDb _marketProfitAndLossDb;
    private readonly EndpointSettings _settings; 
    private string? _sessionToken;

    // Add pagination tracking
    private static readonly int MaxResults = 100;
    private static DateTime _lastFetchTime = DateTime.MinValue;
    private static readonly HashSet<string> FetchedMarketIds = new HashSet<string>();
    private static int _timeWindowRotation; // For rotating time windows

    public MarketApiService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options, MarketProfitAndLossDb marketProfitAndLossDb)
    {
        _httpClient = httpClient;
        _authService = authService; 
        _settings = options.Value;
        _marketProfitAndLossDb = marketProfitAndLossDb;
    }

    private (DateTime fromTime, DateTime toTime) GetRotatingTimeWindow()
    {
        var now = DateTime.UtcNow;

        return _timeWindowRotation switch
        {
            0 => (now, now.AddHours(6)),           // Next 6 hours
            1 => (now.AddHours(6), now.AddHours(12)),   // 6-12 hours ahead
            2 => (now.AddHours(12), now.AddDays(1)),    // 12-24 hours ahead
            3 => (now.AddDays(1), now.AddDays(2)),      // 1-2 days ahead
            _ => (now, now.AddHours(6))
        };
    }

    public async Task<string> ListMarketCatalogue(string? competitionId = null, string? eventId = null)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        // Reset offset daily to ensure we get fresh data
        if (DateTime.UtcNow.Date > _lastFetchTime.Date)
        {
            FetchedMarketIds.Clear();
            _lastFetchTime = DateTime.UtcNow;
            _timeWindowRotation = 0;
        }

        // Rotate through different time windows to get different results
        var (fromTime, toTime) = GetRotatingTimeWindow();

        var filter = new
        {
            competitionIds = competitionId != null ? new[] { competitionId } : null,
            eventTypeIds = new List<string> { "7" },
            // Add rotating time filter to get different markets each call
            marketStartTime = new
            {
                from = fromTime,
                to = toTime
            },
            // Add market status filter to get active markets
            marketStatuses = new[] { "OPEN", "ACTIVE" }
        };

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listMarketCatalogue",
            @params = new
            {
                filter = filter,
                maxResults = MaxResults,
                marketProjection = new[] { "COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA" }
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        response.EnsureSuccessStatusCode();

        var jsonResponse = await response.Content.ReadAsStringAsync();

        // Track fetched markets to avoid duplicates
        await TrackFetchedMarkets(jsonResponse);

        // Increment rotation for next call
        _timeWindowRotation = (_timeWindowRotation + 1) % 4; // Rotate through 4 time windows

        //Console.WriteLine($"Fetched markets for time window {_timeWindowRotation}: {fromTime:yyyy-MM-dd HH:mm} to {toTime:yyyy-MM-dd HH:mm}");
        Console.WriteLine($"Fetched markets for time window {_timeWindowRotation}: {fromTime} to {toTime}");
        Console.WriteLine($"Total unique markets tracked: {FetchedMarketIds.Count}");

        return jsonResponse;
    }

    public async Task<string> ListMarketBookAsync(List<string> marketIds)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();
        const int maxMarketIds = 40; // Betfair allows up to 40 markets per request

        // If we have more than maxMarketIds, batch the requests
        if (marketIds.Count <= maxMarketIds)
        {
            // Single request
            var requestBody = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listMarketBook",
                @params = new
                {
                    marketIds = marketIds,
                    priceProjection = new { priceData = new[] { "EX_BEST_OFFERS" } }
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync();
        }
        else
        {
            // Multiple batched requests
            var allResults = new List<dynamic>();
            
            for (int i = 0; i < marketIds.Count; i += maxMarketIds)
            {
                var batch = marketIds.Skip(i).Take(maxMarketIds).ToList();
                
                var requestBody = new
                {
                    jsonrpc = "2.0",
                    method = "SportsAPING/v1.0/listMarketBook",
                    @params = new
                    {
                        marketIds = batch,
                        priceProjection = new { priceData = new[] { "EX_BEST_OFFERS" } }
                    },
                    id = 1
                };

                _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
                _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

                var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
                var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
                response.EnsureSuccessStatusCode();
                var batchResult = await response.Content.ReadAsStringAsync();
                
                // Parse and combine results
                var batchResponse = JsonSerializer.Deserialize<dynamic>(batchResult);
                if (batchResponse != null)
                {
                    var resultProperty = ((JsonElement)batchResponse).GetProperty("result");
                    if (resultProperty.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var item in resultProperty.EnumerateArray())
                        {
                            allResults.Add(item);
                        }
                    }
                }
                
                // Small delay between batches to avoid rate limiting
                if (i + maxMarketIds < marketIds.Count)
                {
                    await Task.Delay(100);
                }
            }
            
            // Combine all results into a single response
            var combinedResponse = new
            {
                jsonrpc = "2.0",
                result = allResults,
                id = 1
            };
            
            return JsonSerializer.Serialize(combinedResponse);
        }
    }
    /// <summary>
    /// Fetch NCAA Basketball markets from Betfair
    /// Event Type ID 7522 = Basketball (includes NCAA)
    /// </summary>
    public async Task<string> ListBasketballMarketCatalogueAsync(string? competitionId = null, string? eventId = null)
    {
        try
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var now = DateTime.UtcNow;
            var yesterday = now.AddDays(-1);
            var nextWeek = now.AddDays(7);

            var filter = new
            {
                // Basketball Event Type ID
                eventTypeIds = new[] { "7522" },
                competitionIds = competitionId != null ? new[] { competitionId } : null,
                eventIds = eventId != null ? new[] { eventId } : null,
                // Basketball markets: Match Odds (Moneyline), Handicap, Total Points
                marketTypeCodes = new[] { "MATCH_ODDS", "HANDICAP", "TOTAL_POINTS" },
                // Include in-play and pre-match markets
                marketStatuses = new[] { "OPEN", "ACTIVE", "SUSPENDED" },
                // Fetch yesterday (for live games) to next 7 days
                marketStartTime = new { from = yesterday, to = nextWeek }
            };

            var requestBody = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listMarketCatalogue",
                @params = new
                {
                    filter = filter,
                    maxResults = 200, // NCAA has many games per day
                    marketProjection = new[] { "COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA", "MARKET_START_TIME" }
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
            response.EnsureSuccessStatusCode();

            var jsonResponse = await response.Content.ReadAsStringAsync();

            Console.WriteLine($"🏀 Basketball - Fetched markets from yesterday to next week");
            Console.WriteLine($"🏀 Basketball - Response length: {jsonResponse?.Length ?? 0} chars");

            return jsonResponse;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Basketball - Error fetching markets: {ex.Message}");
            throw;
        }
    }

    public async Task<string> ListHorseRacingMarketCatalogueAsync(string? eventTypeId = null, string? eventId = null, DateTime? openDate = null)
    {
        try
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            // Reset tracking daily to ensure we get fresh data for horse racing too
            if (DateTime.UtcNow.Date > _lastFetchTime.Date)
            {
                FetchedMarketIds.Clear();
                _lastFetchTime = DateTime.UtcNow;
                _timeWindowRotation = 0;
            }

            // MODIFIED: Fetch yesterday's races too (to get settled results) + today's races
            var now = DateTime.UtcNow;
            var yesterday = now.AddDays(-1);
            var tomorrow = now.AddDays(1);

            var filter = new
            {
                eventTypeIds = eventTypeId != null ? new[] { eventTypeId } : null,
                eventIds = eventId != null ? new[] { eventId } : null,
                marketTypeCodes = new[] { "WIN", "PLACE" },
                // MODIFIED: Include CLOSED markets (settled races) + active markets
                marketStatuses = new[] { "OPEN", "ACTIVE", "SUSPENDED", "CLOSED" },
                // MODIFIED: Fetch from yesterday to capture settled results
                marketStartTime = new { from = yesterday, to = tomorrow },
                //marketCountries = new[] { "AU", "NZ" } // Include both AU and NZ
            };

            var requestBody = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listMarketCatalogue",
                @params = new
                {
                    filter = filter,
                    maxResults = 200, // Keep higher limit for horse racing
                    marketProjection = new[] { "COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA" }
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
            response.EnsureSuccessStatusCode();

            var jsonResponse = await response.Content.ReadAsStringAsync();

            // Track fetched markets for horse racing too
            await TrackFetchedMarkets(jsonResponse);

            Console.WriteLine($"Horse Racing - Fetched markets from yesterday to tomorrow (including CLOSED markets for results)");
            Console.WriteLine($"Horse Racing - Total unique markets tracked: {FetchedMarketIds.Count}");

            return jsonResponse;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error in ListHorseRacingMarketCatalogueAsync: {ex.Message}");
            return string.Empty;
        }
    }

     public async Task<string> GetMarketProfitAndLossAsync(List<string> marketIds)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();
            
            var requestBody = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listMarketProfitAndLoss",
                @params = new
                {
                    marketIds
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync(); 
        }
      
    public async Task ProcessAndStoreMarketProfitAndLoss(List<string> marketIds)
    {
        try
        {
            var responseJson = await GetMarketProfitAndLossAsync(marketIds);

            var result = JsonSerializer.Deserialize<MarketProfitAndLossApiResponse>(responseJson);

            if (result?.Result?.Count > 0)
            {
                List<MarketProfitAndLoss> marketProfitAndLossList = new List<MarketProfitAndLoss>();

                foreach (var market in result.Result)
                {
                    var marketProfitAndLoss = new MarketProfitAndLoss
                    {
                        MarketId = market.MarketId,
                        ProfitAndLosses = new List<BetProfitAndLoss>()
                    };

                    foreach (var profitLoss in market.ProfitAndLosses)
                    {
                        var betProfitAndLoss = new BetProfitAndLoss
                        {
                            SelectionId = profitLoss.SelectionId,
                            IfWin = profitLoss.IfWin
                        };

                        marketProfitAndLoss.ProfitAndLosses.Add(betProfitAndLoss);
                    }
                    
                    marketProfitAndLossList.Add(marketProfitAndLoss);
                }

                await _marketProfitAndLossDb.InsertMarketProfitAndLossIntoDatabase(marketProfitAndLossList);
            }
            else
            {
                //Console.WriteLine("No market profit and loss data found.");
            }
        }
        catch (Exception ex)
        {
            //Console.WriteLine($"Failed to fetch and store Market Profit and Loss data: {ex.Message}");
        }
    }

    private async Task TrackFetchedMarkets(string jsonResponse)
    {
        try
        {
            using JsonDocument doc = JsonDocument.Parse(jsonResponse);
            if (doc.RootElement.TryGetProperty("result", out JsonElement resultElement) && resultElement.ValueKind == JsonValueKind.Array)
            {
                foreach (var market in resultElement.EnumerateArray())
                {
                    if (market.TryGetProperty("marketId", out JsonElement marketIdElement))
                    {
                        string? marketId = marketIdElement.GetString();
                        if (!string.IsNullOrEmpty(marketId))
                        {
                            FetchedMarketIds.Add(marketId);
                        }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error tracking fetched markets: {ex.Message}");
        }
    }

    public Task<List<string>> GetUnprocessedMarketIds(List<string> allMarketIds)
    {
        // Filter out markets we've already processed recently
        var result = allMarketIds.Where(id => !FetchedMarketIds.Contains(id)).ToList();
        return Task.FromResult(result);
    }
}


public interface IMarketApiService
{
    Task<string> ListMarketCatalogue(string? competitionId = null, string? eventId = null);
    Task<string> ListMarketBookAsync(List<string> marketIds);
    Task<string> GetMarketProfitAndLossAsync(List<string> marketIds);
    Task ProcessAndStoreMarketProfitAndLoss(List<string> marketIds);
    Task<string> ListHorseRacingMarketCatalogueAsync(string? eventTypeId = null, string? eventId = null, DateTime? openDate = null);
    Task<string> ListBasketballMarketCatalogueAsync(string? competitionId = null, string? eventId = null);
    Task<List<string>> GetUnprocessedMarketIds(List<string> allMarketIds);
}
