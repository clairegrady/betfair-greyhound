using System.Text;
using System.Text.Json;
using Betfair.Settings;
using Betfair.Services.Account;
using Microsoft.Extensions.Options;

namespace Betfair.Services;

public interface IResultsService
{
    Task<Dictionary<string, List<RunnerResult>>> GetSettledMarketsAsync(List<string> marketIds);
    Task<List<MarketCatalogueResult>> GetMarketCatalogueAsync(List<string> marketIds);
}

public class ResultsService : IResultsService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly EndpointSettings _settings;
    private readonly ILogger<ResultsService> _logger;

    public ResultsService(
        HttpClient httpClient,
        BetfairAuthService authService,
        IOptions<EndpointSettings> settings,
        ILogger<ResultsService> logger)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = settings.Value;
        _logger = logger;
    }

    public async Task<Dictionary<string, List<RunnerResult>>> GetSettledMarketsAsync(List<string> marketIds)
    {
        var sessionToken = await _authService.GetSessionTokenAsync();
        
        var results = new Dictionary<string, List<RunnerResult>>();

        _logger.LogWarning("🔍 STARTING: Attempting to fetch SETTLED results for {Count} markets: {MarketIds}", marketIds.Count, string.Join(", ", marketIds));

        // IMPORTANT: For settled/closed markets, we DON'T call listMarketCatalogue first!
        // The catalogue doesn't return old markets, but listMarketBook DOES (for 90 days)
        // This is the correct way per Betfair docs: "Retrieving the Result of a Settled Market"
        
        // Call listMarketBook DIRECTLY to get settled results
        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listMarketBook",
            @params = new
            {
                marketIds = marketIds, // Use the original market IDs directly
                priceProjection = new
                {
                    priceData = new[] { "EX_BEST_OFFERS", "SP_AVAILABLE", "SP_TRADED" }
                }
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Remove("X-Application");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);
        _httpClient.DefaultRequestHeaders.Add("X-Application", _authService.AppKey);

        var requestJson = JsonSerializer.Serialize(requestBody);
        _logger.LogWarning("📤 MARKET BOOK REQUEST: {Request}", requestJson);
        
        var content = new StringContent(requestJson, Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        
        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("❌ Betfair API error: {StatusCode}", response.StatusCode);
            var errorBody = await response.Content.ReadAsStringAsync();
            _logger.LogError("❌ Error body: {Body}", errorBody);
            return results;
        }

        var jsonResponse = await response.Content.ReadAsStringAsync();
        _logger.LogWarning("📥 MARKET BOOK RAW RESPONSE: {Response}", jsonResponse);
        
        var apiResponse = JsonSerializer.Deserialize<JsonElement>(jsonResponse);

        if (apiResponse.TryGetProperty("result", out var resultArray))
        {
            var resultCount = resultArray.GetArrayLength();
            _logger.LogWarning("📊 Market book returned {Count} markets", resultCount);
            
            if (resultCount == 0)
            {
                _logger.LogWarning("⚠️ listMarketBook returned ZERO markets!");
                _logger.LogWarning("   Requested: {MarketIds}", string.Join(", ", marketIds));
            }
            
            foreach (var market in resultArray.EnumerateArray())
            {
                var marketId = market.GetProperty("marketId").GetString();
                var marketStatus = market.TryGetProperty("status", out var statusEl) ? statusEl.GetString() : "UNKNOWN";
                
                _logger.LogWarning("   📋 Market {MarketId}: status = {Status}", marketId, marketStatus);
                
                if (string.IsNullOrEmpty(marketId))
                    continue;

                var runnerResults = new List<RunnerResult>();

                if (market.TryGetProperty("runners", out var runners))
                {
                    foreach (var runner in runners.EnumerateArray())
                    {
                        var selectionId = runner.GetProperty("selectionId").GetInt64();
                        var status = runner.TryGetProperty("status", out var statusProp) 
                            ? statusProp.GetString() 
                            : "ACTIVE";

                        // Extract BSP (Betfair Starting Price)
                        double? bsp = null;
                        if (runner.TryGetProperty("sp", out var spProp))
                        {
                            if (spProp.TryGetProperty("actualSP", out var actualSP))
                            {
                                // Handle both number and string formats
                                double tempBsp = 0;
                                bool parsed = false;
                                
                                if (actualSP.ValueKind == JsonValueKind.Number)
                                {
                                    tempBsp = actualSP.GetDouble();
                                    parsed = true;
                                }
                                else if (actualSP.ValueKind == JsonValueKind.String)
                                {
                                    parsed = double.TryParse(actualSP.GetString(), out tempBsp);
                                }
                                
                                // Only set bsp if it's a valid, finite number
                                if (parsed && !double.IsInfinity(tempBsp) && !double.IsNaN(tempBsp))
                                {
                                    bsp = tempBsp;
                                }
                            }
                        }

                        runnerResults.Add(new RunnerResult
                        {
                            SelectionId = selectionId,
                            Status = status ?? "UNKNOWN",
                            RunnerName = null, // We don't have names without catalogue, but status is what matters
                            BSP = bsp
                        });
                        
                        if (status == "WINNER")
                        {
                            _logger.LogWarning("      🏆 WINNER: Selection ID {Id} (Status: {Status}, BSP: {BSP})", selectionId, status, bsp?.ToString() ?? "N/A");
                        }
                    }
                }

                results[marketId] = runnerResults;
            }
        }
        else
        {
            _logger.LogWarning("⚠️ API response has no 'result' property");
        }

        _logger.LogWarning("✅ FINAL: Fetched results for {Count}/{Requested} markets", results.Count, marketIds.Count);
        
        if (results.Count < marketIds.Count)
        {
            var missing = marketIds.Count - results.Count;
            _logger.LogWarning("⚠️ Missing results for {Missing} markets - they may be >90 days old or voided", missing);
        }
        
        return results;
    }

    public async Task<List<MarketCatalogueResult>> GetMarketCatalogueAsync(List<string> marketIds)
    {
        var sessionToken = await _authService.GetSessionTokenAsync();
        var catalogueResults = new List<MarketCatalogueResult>();

        _logger.LogWarning("📋 Fetching market catalogue for {Count} markets", marketIds.Count);

        var catalogueRequest = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listMarketCatalogue",
            @params = new
            {
                filter = new
                {
                    marketIds = marketIds
                },
                maxResults = 200,
                marketProjection = new[] { "RUNNER_DESCRIPTION" }
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Remove("X-Application");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);
        _httpClient.DefaultRequestHeaders.Add("X-Application", _authService.AppKey);

        var content = new StringContent(JsonSerializer.Serialize(catalogueRequest), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        
        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("❌ Catalogue API error: {StatusCode}", response.StatusCode);
            return catalogueResults;
        }

        var jsonResponse = await response.Content.ReadAsStringAsync();
        var apiResponse = JsonSerializer.Deserialize<JsonElement>(jsonResponse);

        if (apiResponse.TryGetProperty("result", out var resultArray))
        {
            foreach (var market in resultArray.EnumerateArray())
            {
                var marketId = market.GetProperty("marketId").GetString();
                if (string.IsNullOrEmpty(marketId))
                    continue;

                var runners = new List<CatalogueRunner>();

                if (market.TryGetProperty("runners", out var runnersArray))
                {
                    foreach (var runner in runnersArray.EnumerateArray())
                    {
                        if (runner.TryGetProperty("selectionId", out var selId) &&
                            runner.TryGetProperty("runnerName", out var name))
                        {
                            runners.Add(new CatalogueRunner
                            {
                                SelectionId = selId.GetInt64(),
                                RunnerName = name.GetString() ?? ""
                            });
                        }
                    }
                }

                catalogueResults.Add(new MarketCatalogueResult
                {
                    MarketId = marketId,
                    Runners = runners
                });
            }
        }

        _logger.LogWarning("✅ Fetched catalogue for {Count} markets", catalogueResults.Count);
        return catalogueResults;
    }
}

public class RunnerResult
{
    public long SelectionId { get; set; }
    public string Status { get; set; } = string.Empty;
    public string? RunnerName { get; set; }
    public double? BSP { get; set; }  // Betfair Starting Price
}

public class MarketCatalogueResult
{
    public string MarketId { get; set; } = string.Empty;
    public List<CatalogueRunner> Runners { get; set; } = new();
}

public class CatalogueRunner
{
    public long SelectionId { get; set; }
    public string RunnerName { get; set; } = string.Empty;
}

