using System.Text.Json;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;

namespace Betfair.Services;
public class CompetitionProcessor
{
    private readonly ICompetitionService _competitionService;
    private readonly CompetitionDb _competitionDb;
    
    public CompetitionProcessor(ICompetitionService competitionService, CompetitionDb competitionDb)
    {
        _competitionService = competitionService;
        _competitionDb = competitionDb;
    }
    public async Task ProcessCompetitionsAsync()
    {
        var competitionsJson = await _competitionService.ListCompetitions();
        var competitionsApiResponse = JsonSerializer.Deserialize<ApiResponse<CompetitionResponse>>(competitionsJson);
        if (competitionsApiResponse != null && competitionsApiResponse.Result != null)
        {
            var competitionResponses = competitionsApiResponse.Result
                .Select(response => new CompetitionResponse
                {
                    Competition = response.Competition,
                    MarketCount = response.MarketCount,
                    CompetitionRegion = response.CompetitionRegion
                })
                .ToList();

            if (competitionResponses.Any())
            {
                await _competitionDb.InsertCompetitionsIntoDatabase(competitionResponses);
            }
            else
            {
                //Console.WriteLine("No competitions to insert.");
            }
        }
        else
        {
            //Console.WriteLine("Failed to deserialize competitions.");
        }
    }
}