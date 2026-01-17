using Microsoft.Data.Sqlite;
using Betfair.Models.Competition;

namespace Betfair.Data;
public class CompetitionDb
{
    private readonly string _connectionString;
    public CompetitionDb(string connectionString)
    {
        _connectionString = connectionString;
    }
    public async Task InsertCompetitionsIntoDatabase(List<CompetitionResponse> competitionResponses)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var competitionResponse in competitionResponses)
        {
            var competition = competitionResponse.Competition;
            using var command = connection.CreateCommand();
            command.CommandText = @"
            INSERT OR REPLACE INTO Competition (Id, Name, MarketCount, CompetitionRegion)
            VALUES ($Id, $Name, $MarketCount, $CompetitionRegion)";

            command.Parameters.AddWithValue("$Id", competition.Id);
            command.Parameters.AddWithValue("$Name", competition.Name);
            command.Parameters.AddWithValue("$MarketCount", competitionResponse.MarketCount);
            command.Parameters.AddWithValue("$CompetitionRegion", competitionResponse.CompetitionRegion);

            await command.ExecuteNonQueryAsync();
        }
    }
}