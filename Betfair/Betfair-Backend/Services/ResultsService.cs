using System.Text.Json;
using Betfair.Services.Interfaces;
using Betfair.Models;
using Betfair.Models.Market;
using Betfair.Models.Runner;

namespace Betfair.Services
{
    public class ResultsService : IResultsService
    {
        private readonly IMarketApiService _marketApiService;
        private readonly ILogger<ResultsService> _logger;

        public ResultsService(IMarketApiService marketApiService, ILogger<ResultsService> logger)
        {
            _marketApiService = marketApiService;
            _logger = logger;
        }

        public async Task<List<MarketBook<ApiRunner>>> GetSettledMarkets(List<string> marketIds)
        {
            try
            {
                _logger.LogInformation("Fetching settled market results for {Count} markets", marketIds.Count);
                
                // Call Betfair API to get settled market data
                var response = await _marketApiService.ListMarketBookAsync(marketIds);
                
                // Parse the response
                var marketBookResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(response);
                
                if (marketBookResponse?.Result != null)
                {
                    _logger.LogWarning("Successfully retrieved {Count} settled markets", marketBookResponse.Result.Count());
                    return marketBookResponse.Result.ToList();
                }
                
                _logger.LogWarning("No settled market data returned from API");
                return new List<MarketBook<ApiRunner>>();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching settled markets");
                throw;
            }
        }
    }
}