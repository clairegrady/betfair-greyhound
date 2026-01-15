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

                // Set busy timeout to 30 seconds to handle concurrent writes
                using (var timeoutCommand = connection.CreateCommand())
                {
                    timeoutCommand.CommandText = "PRAGMA busy_timeout = 30000;";
                    await timeoutCommand.ExecuteNonQueryAsync();
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
    
    public async Task<MarketCatalogue?> GetMarketCatalogueByMarketId(string marketId)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();
        
        using var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT MarketId, MarketName, EventName, OpenDate, EventId
            FROM MarketCatalogue 
            WHERE MarketId = $MarketId";
        command.Parameters.AddWithValue("$MarketId", marketId);
        
        using var reader = await command.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
        {
            return null;
        }
        
        var catalogue = new MarketCatalogue
        {
            MarketId = reader.GetString(0),
            MarketName = !reader.IsDBNull(1) ? reader.GetString(1) : null,
            Event = new Models.Event.Event
            {
                Name = !reader.IsDBNull(2) ? reader.GetString(2) : null,
                OpenDate = !reader.IsDBNull(3) ? DateTime.Parse(reader.GetString(3)) : null,
                Id = !reader.IsDBNull(4) ? reader.GetString(4) : null
            },
            Runners = new List<Models.Runner.RunnerDescription>()
        };
        
        // Runners are stored in the in-memory catalogue, not in a separate table
        // The marketCatalogues passed to InsertMarketsIntoDatabase contain runners
        // but we only save the market-level data to the database
        // 
        // Solution: We need to get runner names directly from the Betfair API response
        // when processing market books, not from the database
        
        return catalogue;
    }
}

