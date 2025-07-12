using System.Text;
using System.Text.Json;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services.Account;
public class AccountService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly EndpointSettings _settings;
    
    public AccountService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = options.Value;
    }
    public async Task<string> GetAccountFundsAsync()
    {
        var sessionToken = await _authService.GetSessionTokenAsync();

        var request = new
        {
            jsonrpc = "2.0",
            method = "AccountAPING/v1.0/getAccountFunds",
            @params = new { },
            id = 1
        };
        
        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(request), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.AccountEndpoint, content);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"Failed to fetch account funds: {errorContent}");
            throw new HttpRequestException($"Error fetching account funds: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;  
    }
    public async Task<string> GetAccountDetailsAsync()
    {
        var sessionToken = await _authService.GetSessionTokenAsync();

        var request = new
        {
            jsonrpc = "2.0",
            method = "AccountAPING/v1.0/getAccountDetails",
            @params = new { },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(request), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.AccountEndpoint, content);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"Failed to fetch account details: {errorContent}");
            throw new HttpRequestException($"Error fetching account details: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;  
    }

    public async Task<string> GetAccountStatementAsync(string locale, int recordCount, BetfairAutomationServicePlaceOrder.TimeRange itemDateRange, string includeItem, string wallet)
    {
        var sessionToken = await _authService.GetSessionTokenAsync();

        var request = new
        {
            jsonrpc = "2.0",
            method = "AccountAPING/v1.0/getAccountStatement",
            @params = new
            {
                locale = locale,
                recordCount = recordCount,
                itemDateRange = itemDateRange,  
                includeItem = includeItem,     
                wallet = wallet               
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(request), Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(_settings.AccountEndpoint, content);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"Failed to fetch account statement: {errorContent}");
            throw new HttpRequestException($"Error fetching account statement: {response.StatusCode} - {errorContent}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;  
    }
}
