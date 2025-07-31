using Microsoft.Data.Sqlite;
using Betfair.Models.Market;

namespace Betfair.Data;
public class ListMarketCatalogueDb
{
    private readonly string _connectionString;
    public ListMarketCatalogueDb(string connectionString)
    {
        _connectionString = connectionString;
    }

    public async Task InsertMarketsIntoDatabase(List<MarketCatalogue> marketCatalogues)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var marketCatalogue in marketCatalogues)
        {
            //Console.WriteLine($"MarketId: {marketCatalogue.MarketId}, MarketName: {marketCatalogue.MarketName}");

            if (marketCatalogue.Runners != null && marketCatalogue.Runners.Any())
            {
                //Console.WriteLine($"Runners for MarketId {marketCatalogue.MarketId}:");
                foreach (var runner in marketCatalogue.Runners)
                {
                    //Console.WriteLine($" - RunnerId: {runner.RunnerId}, Name: {runner.RunnerName}, Form: {runner.Metadata?.Form}");
                }
            }
            else
            {
                //Console.WriteLine("No runners found for this market.");
            }


            using var command = connection.CreateCommand();
            command.CommandText = @"
                INSERT OR REPLACE INTO MarketCatalogue 
                (MarketId, MarketName, TotalMatched, EventId, EventName, CountryCode, Timezone, OpenDate, EventTypeId, EventTypeName, CompetitionId, CompetitionName)
                VALUES 
                ($MarketId, $MarketName, $TotalMatched, $EventId, $EventName, $CountryCode, $Timezone, $OpenDate, $EventTypeId, $EventTypeName, $CompetitionId, $CompetitionName)";

            command.Parameters.AddWithValue("$MarketId", marketCatalogue.MarketId ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$MarketName", marketCatalogue.MarketName ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$TotalMatched", marketCatalogue.TotalMatched ?? (object)DBNull.Value);

            command.Parameters.AddWithValue("$EventId", marketCatalogue.Event?.Id ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$EventName", marketCatalogue.Event?.Name ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$CountryCode", marketCatalogue.Event?.CountryCode ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$Timezone", marketCatalogue.Event?.Timezone ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$OpenDate", marketCatalogue.Event?.OpenDate.HasValue == true 
                ? (object)marketCatalogue.Event.OpenDate.Value.ToString("yyyy-MM-ddTHH:mm:ssZ") 
                : DBNull.Value);

            command.Parameters.AddWithValue("$EventTypeId", marketCatalogue.EventType?.Id ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$EventTypeName", marketCatalogue.EventType?.Name ?? (object)DBNull.Value);

            command.Parameters.AddWithValue("$CompetitionId", marketCatalogue.Competition?.Id ?? (object)DBNull.Value);
            command.Parameters.AddWithValue("$CompetitionName", marketCatalogue.Competition?.Name ?? (object)DBNull.Value);

            await command.ExecuteNonQueryAsync();
        }
    }
}

