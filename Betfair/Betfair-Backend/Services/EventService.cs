using System.Text;
using System.Text.Json;
using Betfair.Models;
using Betfair.Models.Event;
using Betfair.Services.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services;
public class EventService : IEventService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly EndpointSettings _settings;
    private string _sessionToken;

    public EventService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = options.Value;
    }

    public async Task<string> ListEventTypes()
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        // Define the MarketFilter with specific eventTypeIds (example with event types 1 and 2)
        // var marketFilter = new 
        // {
        //     eventTypeIds = new[] { 1, 2 } // Example: filter for event types with IDs 1 and 2
        // };

        var marketFilter = new { };

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listEventTypes",
            @params = new 
            {
                filter = marketFilter, 
                locale = "en_GB"
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        response.EnsureSuccessStatusCode();
        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;
    }
    
    public async Task<string> ListEvents(List<string> eventTypeIds)
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 
        
        var marketFilter = new
        {
            eventTypeIds = eventTypeIds,
        };

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listEvents",
            @params = new
            {
                filter = marketFilter,
                locale = "en_GB"
            },
            id = 1
        };
        
        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        response.EnsureSuccessStatusCode();
        var responseContent = await response.Content.ReadAsStringAsync();
        return responseContent;
    }

    public async Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertEventTypesAsync(int eventId)
    {
        try
        {
            var responseContent = await ListEventTypes();

            var apiResponse = JsonSerializer.Deserialize<ApiResponse<EventTypeResult>>(responseContent);

            if (apiResponse == null || apiResponse.Result == null || !apiResponse.Result.Any())
            {
                return (false, "No event type data available.");
            }

            var eventTypes = apiResponse.Result
                .Select(e => new EventType
                {
                    Id = e.EventType.Id,
                    Name = e.EventType.Name
                })
                .ToList();

            //InsertEventTypesIntoDatabase(eventTypeResponses);
            return (true, string.Empty);
        }
        catch (Exception ex)
        {
            return (false, "Internal server error");
        }
    }
}

public interface IEventService
{
    Task<string> ListEventTypes();

    Task<string> ListEvents(List<string> eventTypeIds);

    Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertEventTypesAsync(int eventId);
}
