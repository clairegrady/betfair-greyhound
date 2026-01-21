using Npgsql;
using Betfair.Models.Event;
using Betfair.Models.Market;

namespace Betfair.Data;
public class EventDb2
{
    private readonly string _connectionString;
    public EventDb2(string connectionString)
    {
        _connectionString = connectionString;
    }
    public async Task InsertEventTypesAsync(List<EventTypeResult> eventTypes)
    {
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var eventTypeResult in eventTypes)
        {
            using var command = connection.CreateCommand();
            command.CommandText = @"
                INSERT INTO eventtype (id, name, marketcount)
                VALUES (@id, @name, @marketcount)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    marketcount = EXCLUDED.marketcount";

            command.Parameters.AddWithValue("@id", long.Parse(eventTypeResult.EventType.Id));
            command.Parameters.AddWithValue("@name", eventTypeResult.EventType.Name);
            command.Parameters.AddWithValue("@marketcount", eventTypeResult.MarketCount);

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

    using var connection = new NpgsqlConnection(_connectionString);
    await connection.OpenAsync();
   //Console.WriteLine($"DEBUG: Opened PostgreSQL connection to {_connectionString}");

    int insertCount = 0;
    int skippedCount = 0;

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

       //Console.WriteLine($"DEBUG: Inserting MarketId: {marketId}, MarketName: {marketName}, EventName: {evName}");

        using var cmd = connection.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO eventmarkets (eventid, marketid, marketname, eventname)
            VALUES (@eventid, @marketid, @marketname, @eventname)
            ON CONFLICT (eventid, marketid) DO NOTHING";

        cmd.Parameters.AddWithValue("@eventid", long.Parse(eventId));
        cmd.Parameters.AddWithValue("@marketid", marketId);
        cmd.Parameters.AddWithValue("@marketname", marketName);
        cmd.Parameters.AddWithValue("@eventname", evName);

        try
        {
            int rowsAffected = await cmd.ExecuteNonQueryAsync();
            if (rowsAffected > 0)
            {
                insertCount++;
                Console.WriteLine($"✅ Inserted EventMarket: {marketId} into EventMarkets");
            }
            else
            {
                Console.WriteLine($"⚠️  MarketId {marketId} already exists in EventMarkets (duplicate)");
                skippedCount++;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Error inserting EventMarket {marketId}: {ex.Message}");
        }
    }

   //Console.WriteLine($"DEBUG: Finished inserting EventMarkets: {insertCount} inserted, {skippedCount} skipped.");
}
    public async Task InsertEventListAsync(List<EventListResult> events, string sport)
    {
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var eventResult in events)
        {
            using var command = connection.CreateCommand();
            command.CommandText = @"
            INSERT INTO eventlist (
                id, name, countrycode, timezone, opendate, marketcount, sport
            )
            VALUES (
                @id, @name, @countrycode, @timezone, @opendate, @marketcount, @sport
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                countrycode = EXCLUDED.countrycode,
                timezone = EXCLUDED.timezone,
                opendate = EXCLUDED.opendate,
                marketcount = EXCLUDED.marketcount,
                sport = EXCLUDED.sport";

            command.Parameters.AddWithValue("@id", long.Parse(eventResult.Event.Id));
            command.Parameters.AddWithValue("@name", eventResult.Event.Name);
            command.Parameters.AddWithValue("@countrycode", (object?)eventResult.Event.CountryCode ?? DBNull.Value);
            command.Parameters.AddWithValue("@timezone", (object?)eventResult.Event.Timezone ?? DBNull.Value);
            command.Parameters.AddWithValue("@opendate", eventResult.Event.OpenDate);
            command.Parameters.AddWithValue("@marketcount", eventResult.MarketCount);
            command.Parameters.AddWithValue("@sport", (object?)sport ?? DBNull.Value);

            await command.ExecuteNonQueryAsync();
        }
    }

    public async Task UpdateEventListWithMarketIdsAsync()
    {
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        using var command = connection.CreateCommand();
        command.CommandText = @"
        UPDATE eventlist
        SET marketid = (
            SELECT marketid
            FROM eventmarkets
            WHERE eventmarkets.eventid = eventlist.id::text
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM eventmarkets
            WHERE eventmarkets.eventid = eventlist.id::text
        )";

        await command.ExecuteNonQueryAsync();
    }
}

