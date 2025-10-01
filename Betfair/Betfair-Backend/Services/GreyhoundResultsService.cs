using Betfair.Services.Interfaces;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Betfair.Models;
using System.Text.Json;

namespace Betfair.Services;

public class GreyhoundResultsService : IResultsService
{
    private readonly IMarketApiService _marketApiService;
    private readonly ILogger<GreyhoundResultsService> _logger;

    public GreyhoundResultsService(IMarketApiService marketApiService, ILogger<GreyhoundResultsService> logger)
    {
        _marketApiService = marketApiService;
        _logger = logger;
    }

    public async Task<List<MarketBook<ApiRunner>>> GetSettledMarkets(List<string> marketIds)
    {
        try
        {
            _logger.LogInformation("Fetching settled greyhound markets for {Count} market IDs", marketIds.Count);

            // Filter to greyhound markets (event type 4339)
            var greyhoundMarketIds = marketIds.Where(id => IsGreyhoundMarket(id)).ToList();
            
            if (!greyhoundMarketIds.Any())
            {
                _logger.LogWarning("No greyhound market IDs found in the provided list");
                return new List<MarketBook<ApiRunner>>();
            }

            _logger.LogInformation("Processing {Count} greyhound market IDs", greyhoundMarketIds.Count);

            // Fetch market books for greyhound markets
            var marketBookJson = await _marketApiService.ListMarketBookAsync(greyhoundMarketIds);
            
            if (string.IsNullOrEmpty(marketBookJson))
            {
                _logger.LogWarning("Empty response from market API for greyhound markets");
                return new List<MarketBook<ApiRunner>>();
            }

            var marketBookResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
            
            if (marketBookResponse?.Result == null)
            {
                _logger.LogWarning("Failed to deserialize market book response for greyhound markets");
                return new List<MarketBook<ApiRunner>>();
            }

            // Filter for settled markets only
            var settledMarkets = marketBookResponse.Result
                .Where(market => market.Status == "CLOSED" || market.Status == "SUSPENDED")
                .Where(market => market.Runners?.Any(runner => 
                    runner.Status == "WINNER" || 
                    runner.Status == "LOSER" || 
                    runner.Status == "PLACED") == true)
                .ToList();

            _logger.LogInformation("Found {Count} settled greyhound markets", settledMarkets.Count);
            
            return settledMarkets;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching settled greyhound markets");
            return new List<MarketBook<ApiRunner>>();
        }
    }

    private bool IsGreyhoundMarket(string marketId)
    {
        // Greyhound markets typically start with specific prefixes
        // This is a heuristic - you may need to adjust based on actual market ID patterns
        return marketId.StartsWith("1.2") && marketId.Length > 10;
    }

    public async Task<List<MarketBook<ApiRunner>>> GetGreyhoundSettledMarkets(List<string> marketIds)
    {
        return await GetSettledMarkets(marketIds);
    }

    public async Task<MarketBook<ApiRunner>?> GetGreyhoundMarketResult(string marketId)
    {
        try
        {
            var marketBooks = await GetSettledMarkets(new List<string> { marketId });
            return marketBooks.FirstOrDefault();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching greyhound market result for {MarketId}", marketId);
            return null;
        }
    }
}
