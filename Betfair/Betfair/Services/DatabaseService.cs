using Betfair.Handlers;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Microsoft.Data.Sqlite;
using Dapper;

namespace Betfair.Services;

public class DatabaseService
{
    private readonly string _connectionString;

    public DatabaseService(string connectionString)
    {
        _connectionString = connectionString;
    }

    public IEnumerable<Event> GetEventList()
    {
        using var connection = new SqliteConnection(_connectionString);
        const string query = "SELECT * FROM EventList";
        return connection.Query<Event>(query);
    }

    public IEnumerable<MarketCatalogueDisplayDto> GetMarketCatalogueList()
    {
        using var connection = new SqliteConnection(_connectionString);
        const string query = @"
                SELECT m.MarketId, m.MarketName, m.TotalMatched,
                       e.Id AS EventId, e.Name AS EventName, e.CountryCode, e.Timezone, e.OpenDate,
                       et.Id AS EventTypeId, et.Name AS EventTypeName,
                       c.Id AS CompetitionId, c.Name AS CompetitionName
                FROM MarketCatalogue m
                JOIN EventList e ON m.EventId = e.Id
                JOIN EventType et ON m.EventTypeId = et.Id
                JOIN Competition c ON m.CompetitionId = c.Id";

        return connection
            .Query<MarketCatalogueDisplayDto, EventDisplayDto, EventTypeDisplayDto, CompetitionDisplayDto,
                MarketCatalogueDisplayDto>(
                query,
                (market, eventItem, eventType, competition) =>
                {
                    market.Event = eventItem;
                    market.EventType = eventType;
                    market.Competition = competition;
                    return market;
                },
                splitOn: "EventId,EventTypeId,CompetitionId"
            );
    }

    public async Task DisplayMarketBooks(IEnumerable<string> marketIds)
    {
        if (marketIds == null || !marketIds.Any())
        {
            Console.WriteLine("No market IDs provided.");
            return;
        }

        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        var displayHandler = new DisplayHandler();

        foreach (var marketId in marketIds)
        {
            Console.WriteLine(new string('*', 215));
            
            const string query = @"
            SELECT 
                mc.MarketId, 
                mc.MarketName, 
                mc.TotalMatched, 
                mc.EventName,
                mbr.Id AS BackPriceId,
                mbr.SelectionId, 
                mbr.Status, 
                mbr.LastPriceTraded,
                mbr.Price AS BackPrice, 
                mbr.Size AS BackSize,
                mbl.Id AS LayPriceId,
                mbl.Price AS LayPrice, 
                mbl.Size AS LaySize
            FROM 
                MarketBookBackPrices mbr
            INNER JOIN 
                MarketBookLayPrices mbl ON mbr.Id = mbl.Id
            INNER JOIN 
                MarketCatalogue mc ON mc.MarketId = mbr.MarketId
            WHERE 
                mc.MarketId = @MarketId";

            using var command = new SqliteCommand(query, connection);
            command.Parameters.AddWithValue("@MarketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            displayHandler.DisplayHeader();

            while (await reader.ReadAsync())
            {
                displayHandler.DisplayMarketBookRow(reader);
            }
            displayHandler.DisplayFooter();
        }
    }
}