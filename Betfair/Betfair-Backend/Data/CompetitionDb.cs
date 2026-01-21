using Npgsql;
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
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var competitionResponse in competitionResponses)
        {
            var competition = competitionResponse.Competition;
            using var command = connection.CreateCommand();
            command.CommandText = @"
            INSERT INTO competition (id, name, marketcount, competitionregion)
            VALUES (@id, @name, @marketcount, @competitionregion)
            ON CONFLICT (id) DO UPDATE SET 
                name = EXCLUDED.name,
                marketcount = EXCLUDED.marketcount,
                competitionregion = EXCLUDED.competitionregion";

            command.Parameters.AddWithValue("@id", competition.Id);
            command.Parameters.AddWithValue("@name", competition.Name);
            command.Parameters.AddWithValue("@marketcount", competitionResponse.MarketCount);
            command.Parameters.AddWithValue("@competitionregion", competitionResponse.CompetitionRegion);

            await command.ExecuteNonQueryAsync();
        }
    }
}