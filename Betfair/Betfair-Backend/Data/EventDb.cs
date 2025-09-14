using Microsoft.Data.Sqlite;
using Betfair.Models.Event;
using Betfair.Models.Market;
using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;

namespace Betfair.Data
{
    public class EventDb
    {
        private readonly string _connectionString;

        public EventDb(string connectionString)
        {
            _connectionString = connectionString;
        }

        public async Task InsertEventTypesAsync(List<EventTypeResult> eventTypes)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            foreach (var eventTypeResult in eventTypes)
            {
                using var command = connection.CreateCommand();
                command.CommandText = @"
                    INSERT OR REPLACE INTO EventType (Id, Name, MarketCount)
                    VALUES ($Id, $Name, $MarketCount);
                ";

                command.Parameters.AddWithValue("$Id", eventTypeResult.EventType.Id);
                command.Parameters.AddWithValue("$Name", eventTypeResult.EventType.Name);
                command.Parameters.AddWithValue("$MarketCount", eventTypeResult.MarketCount);

                await command.ExecuteNonQueryAsync();
            }
        }

        public async Task InsertEventMarketsAsync(string eventId, string eventName, List<MarketCatalogue> markets)
        {
            if (string.IsNullOrEmpty(eventId))
            {
               //Console.WriteLine("DEBUG: eventId is null or empty!");
                return;
            }

            if (markets == null || markets.Count == 0)
            {
               //Console.WriteLine("DEBUG: markets list is null or empty!");
                return;
            }

            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();
           //Console.WriteLine($"DEBUG: Opened SQLite connection to {_connectionString}");

            int insertCount = 0;
            int skippedCount = 0;

            // Log existing MarketIds in EventMarkets
            await LogExistingMarketIds(connection);

            foreach (var market in markets)
            {
                if (market == null)
                {
                   //Console.WriteLine("DEBUG: market object is null, skipping...");
                    skippedCount++;
                    continue;
                }

                string marketId = market.MarketId;
                string marketName = market.MarketName;
                string evName = eventName;

                // Defensive checks
                if (string.IsNullOrEmpty(marketId))
                {
                   //Console.WriteLine("DEBUG: market.MarketId is null or empty, skipping...");
                    skippedCount++;
                    continue;
                }
                if (string.IsNullOrEmpty(marketName))
                {
                   //Console.WriteLine($"DEBUG: market.MarketName is null or empty for MarketId {marketId}, setting to 'Unknown'");
                    marketName = "Unknown";
                }
                if (string.IsNullOrEmpty(evName))
                {
                   //Console.WriteLine($"DEBUG: eventName is null or empty, setting to 'Unknown'");
                    evName = "Unknown";
                }

                // Check if the MarketId already exists
                if (await IsMarketIdExistsAsync(connection, marketId))
                {
                   //Console.WriteLine($"DEBUG: MarketId {marketId} already exists, skipping insert.");
                    skippedCount++;
                    continue;
                }

               //Console.WriteLine($"DEBUG: Inserting MarketId: {marketId}, MarketName: {marketName}, EventName: {evName}");

                using var cmd = connection.CreateCommand();
                cmd.CommandText = @"
                    INSERT OR REPLACE INTO EventMarkets (EventId, MarketId, MarketName, EventName)
                    VALUES ($EventId, $MarketId, $MarketName, $EventName);
                ";

                cmd.Parameters.AddWithValue("$EventId", eventId);
                cmd.Parameters.AddWithValue("$MarketId", marketId);
                cmd.Parameters.AddWithValue("$MarketName", marketName);
                cmd.Parameters.AddWithValue("$EventName", evName);

                try
                {
                    int rowsAffected = await cmd.ExecuteNonQueryAsync();
                    if (rowsAffected > 0)
                    {
                        insertCount++;
                       //Console.WriteLine($"DEBUG: Inserted MarketId {marketId} successfully.");
                    }
                    else
                    {
                       //Console.WriteLine($"DEBUG: MarketId {marketId} insert ignored (likely duplicate).");
                        skippedCount++;
                    }
                }
                catch (Exception ex)
                {
                   //Console.WriteLine($"ERROR: Exception inserting MarketId {marketId}: {ex.Message}");
                }
            }

           //Console.WriteLine($"DEBUG: Finished inserting EventMarkets: {insertCount} inserted, {skippedCount} skipped.");
        }

        public async Task InsertEventListAsync(List<EventListResult> events, string sport)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            foreach (var eventResult in events)
            {
                using var command = connection.CreateCommand();
                command.CommandText = @"
                INSERT OR REPLACE INTO EventList (
                    Id, Name, CountryCode, Timezone, OpenDate, MarketCount, Sport
                )
                VALUES (
                    $Id, $Name, $CountryCode, $Timezone, $OpenDate, $MarketCount, $Sport
                );
            ";

                command.Parameters.AddWithValue("$Id", eventResult.Event.Id);
                command.Parameters.AddWithValue("$Name", eventResult.Event.Name);
                command.Parameters.AddWithValue("$CountryCode", eventResult.Event.CountryCode ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Timezone", eventResult.Event.Timezone ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$OpenDate", eventResult.Event.OpenDate);
                command.Parameters.AddWithValue("$MarketCount", eventResult.MarketCount);
                command.Parameters.AddWithValue("$Sport", sport ?? (object)DBNull.Value);

                await command.ExecuteNonQueryAsync();
            }
        }

        public async Task UpdateEventListWithMarketIdsAsync()
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            using var command = connection.CreateCommand();
            command.CommandText = @"
            UPDATE EventList
            SET MarketId = (
                SELECT MarketId
                FROM EventMarkets
                WHERE EventMarkets.EventId = EventList.Id
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1
                FROM EventMarkets
                WHERE EventMarkets.EventId = EventList.Id
            );
        ";

            await command.ExecuteNonQueryAsync();
        }

        // Helper method to check if a MarketId exists in the EventMarkets table
        private async Task<bool> IsMarketIdExistsAsync(SqliteConnection connection, string marketId)
        {
            using var checkCmd = connection.CreateCommand();
            checkCmd.CommandText = @"
                SELECT COUNT(*) 
                FROM EventMarkets 
                WHERE MarketId = $MarketId;
            ";
            checkCmd.Parameters.AddWithValue("$MarketId", marketId);
            int count = Convert.ToInt32(await checkCmd.ExecuteScalarAsync());
            return count > 0;
        }

        // Helper method to log existing MarketIds in the EventMarkets table
        private async Task LogExistingMarketIds(SqliteConnection connection)
        {
            using var checkCmd = connection.CreateCommand();
            checkCmd.CommandText = "SELECT MarketId FROM EventMarkets";
            using var reader = await checkCmd.ExecuteReaderAsync();

           //Console.WriteLine("DEBUG: Existing MarketIds in EventMarkets:");
            while (await reader.ReadAsync())
            {
               //Console.WriteLine($"MarketId: {reader.GetString(0)}");
            }
        }
    }
}
