using System.Text;
using System.Text.Json;
using Betfair.Models.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services.Account;
public class OrderService : IOrderService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly EndpointSettings _settings;
    private string _sessionToken;

    public OrderService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = options.Value;
    }
    
    public async Task<string> PlaceOrdersAsync(string marketId, string selectionId, double price, double size, string side)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var placeOrdersRequest = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/placeOrders",
            @params = new
            {
                marketId,
                instructions = new[]
                {
                    new
                    {
                        selectionId,
                        side,
                        orderType = "LIMIT",
                        limitOrder = new
                        {
                            price,
                            size,
                            persistenceType = "PERSIST"
                        }
                    }
                }
            },
            id = 1
        };
        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(placeOrdersRequest), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            //Console.WriteLine($"Failed to place order: {errorContent}");
            throw new HttpRequestException($"Error placing order: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;
    }
    
    public async Task<string> CancelOrderAsync(string marketId, List<CancelInstruction> instructions = null, string customerRef = null)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var cancelInstructions = new List<CancelInstruction>
        {
            new CancelInstruction
            {
                betId = "372606848835",
                size = "10" 
            }
        };

        var cancelOrdersRequest = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/cancelOrders",
            @params = new
            {
                marketId = marketId,
                instructions = new List<CancelInstruction>(cancelInstructions),
                customerRef = customerRef
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(cancelOrdersRequest), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            //Console.WriteLine($"Failed to cancel order(s): {errorContent}");
            throw new HttpRequestException($"Error canceling order(s): {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        //Console.WriteLine($"Cancel order response: {responseContent}");

        return responseContent;
    }
    
    public async Task<string> UpdateOrdersAsync(string marketId, List<UpdateInstruction> instructions, string customerRef = null)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var updateInstruction = new UpdateInstruction
        {
            betId = "1.23456789", 
            size = 10.0,           
            price = 2.5            
        };

        var updateOrdersRequest = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/updateOrders",
            @params = new
            {
                marketId = marketId,
                instructions = new List<UpdateInstruction> { updateInstruction },
                customerRef = customerRef
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(updateOrdersRequest), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            //Console.WriteLine($"Failed to update orders: {errorContent}");
            throw new HttpRequestException($"Error updating orders: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        //Console.WriteLine($"Update orders response: {responseContent}");

        return responseContent;
    }

    public async Task<string> ReplaceOrdersAsync(string marketId, List<ReplaceInstruction> instructions, string customerRef = null, MarketVersion marketVersion = null, bool async = false)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var replaceInstruction = new ReplaceInstruction
        {
            betId = "1.23456789", 
            price = 2.5,           
            size = 10.0,           
            side = "BACK"         
        };

        var replaceOrdersRequest = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/replaceOrders",
            @params = new
            {
                marketId = marketId,
                instructions = new List<ReplaceInstruction> { replaceInstruction },
                customerRef = customerRef,
                marketVersion = marketVersion,
                async = async
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(replaceOrdersRequest), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            //Console.WriteLine($"Failed to replace orders: {errorContent}");
            throw new HttpRequestException($"Error replacing orders: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        //Console.WriteLine($"Replace orders response: {responseContent}");

        return responseContent;
    }
}

public interface IOrderService
{
    Task<string> PlaceOrdersAsync(string marketId, string selectionId, double price, double size, string side);
    Task<string> CancelOrderAsync(string marketId, List<CancelInstruction> instructions = null, string customerRef = null);
    Task<string> UpdateOrdersAsync(string marketId, List<UpdateInstruction> instructions, string customerRef = null);
    Task<string> ReplaceOrdersAsync(string marketId, List<ReplaceInstruction> instructions, string customerRef = null, MarketVersion marketVersion = null, bool async = false);
}
