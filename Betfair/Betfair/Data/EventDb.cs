using Microsoft.Data.Sqlite;
using Betfair.Models.Event;

namespace Betfair.Data;
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
}

