using System.Text;
using System.Text.Json;
using Betfair.Data;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services;
public class MarketService : IMarketService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly MarketProfitAndLossDb _marketProfitAndLossDb;
    private readonly EndpointSettings _settings; 
    private string _sessionToken;

    public MarketService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options, MarketProfitAndLossDb marketProfitAndLossDb)
    {
        _httpClient = httpClient;
        _authService = authService; 
        _settings = options.Value;
        _marketProfitAndLossDb = marketProfitAndLossDb;
    }

    public async Task<string> ListMarketCatalogue(string competitionId = null, string eventId = null)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var filter = new
        {
            competitionIds = competitionId != null ? new[] { competitionId } : null,
            eventIds = eventId != null ? new[] { eventId } : null
        };

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listMarketCatalogue",
            @params = new
            {
                filter = filter,
                maxResults = 1000,
                marketProjection = new[] { "COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA" }
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

    public async Task<string> ListMarketBookAsync(List<string> marketIds)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();
        const int maxMarketIds = 10;

        var limitedMarketIds = marketIds.Take(maxMarketIds).ToList();

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listMarketBook",
            @params = new
            {
                marketIds = limitedMarketIds,
                priceProjection = new { priceData = new[] { "EX_BEST_OFFERS", "EX_TRADED" } }
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
                Console.WriteLine("No market profit and loss data found.");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to fetch and store Market Profit and Loss data: {ex.Message}");
        }
    }
}

public interface IMarketService
{
}