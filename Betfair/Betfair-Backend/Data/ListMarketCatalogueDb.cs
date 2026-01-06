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
        Console.WriteLine("##################################################################");
        
        // Retry logic for database lock errors
        int maxRetries = 5;
        int retryDelayMs = 100;
        
        for (int attempt = 0; attempt < maxRetries; attempt++)
        {
            try
            {
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();
                
                // Enable WAL mode for better concurrency
                using (var walCommand = connection.CreateCommand())
                {
                    walCommand.CommandText = "PRAGMA journal_mode=WAL;";
                    await walCommand.ExecuteNonQueryAsync();
                }

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
                
                // Success - break out of retry loop
                return;
            }
            catch (SqliteException ex) when (ex.SqliteErrorCode == 5 && attempt < maxRetries - 1) // SQLite BUSY
            {
                Console.WriteLine($"⚠️ Database locked (attempt {attempt + 1}/{maxRetries}), retrying in {retryDelayMs}ms...");
                await Task.Delay(retryDelayMs);
                retryDelayMs *= 2; // Exponential backoff
            }
        }
        
        // If we get here, all retries failed
        throw new Exception("Failed to insert market catalogues after multiple retries due to database lock");
    }
}

