using System.Text;
using System.Text.Json;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Services.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services;
public class CompetitionService : ICompetitionService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService; 
    private readonly CompetitionDb _competitionDb; 
    private readonly EndpointSettings _settings;
    private string _sessionToken;

    public CompetitionService(HttpClient httpClient, BetfairAuthService authService, IOptions<EndpointSettings> options, CompetitionDb competitionDb)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = options.Value;
        _competitionDb = competitionDb;
    }

    public async Task<string> ListCompetitions()
    {
        _sessionToken = await _authService.GetSessionTokenAsync(); 

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "SportsAPING/v1.0/listCompetitions",
            @params = new { filter = new { } },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
        _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync();  
    }

    public async Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertCompetitionsAsync()
    {
        try
        {
            var responseContent = await ListCompetitions();

            var apiResponse = JsonSerializer.Deserialize<ApiResponse<CompetitionResponse>>(responseContent);

            if (apiResponse == null || apiResponse.Result == null || !apiResponse.Result.Any())
            {
                return (false, "No competition data available.");
            }

            var competitionResponses = apiResponse.Result
                .Select(c => new CompetitionResponse
                {
                    Competition = new Competition
                    {
                        Id = c.Competition.Id,
                        Name = c.Competition.Name,
                    },
                    MarketCount = c.MarketCount,
                    CompetitionRegion = c.CompetitionRegion
                })
                .ToList();

             await _competitionDb.InsertCompetitionsIntoDatabase(competitionResponses);

            return (true, string.Empty);
        }
        catch (Exception ex)
        {
            return (false, "Internal server error");
        }
    }
}

public interface ICompetitionService
{
    Task<string> ListCompetitions();
    Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertCompetitionsAsync();
}