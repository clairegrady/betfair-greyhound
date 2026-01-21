using Betfair.Handlers;
using Betfair.Models;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Npgsql;
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
        using var connection = new NpgsqlConnection(_connectionString);
        const string query = "SELECT * FROM eventlist";
        return connection.Query<Event>(query);
    }

    public IEnumerable<MarketCatalogueDisplayDto> GetMarketCatalogueList()
    {
        using var connection = new NpgsqlConnection(_connectionString);
        const string query = @"
                SELECT m.marketid, m.marketname, m.totalmatched,
                       e.id AS eventid, e.name AS eventname, e.countrycode, e.timezone, e.opendate,
                       et.id AS eventtypeid, et.name AS eventtypename,
                       c.id AS competitionid, c.name AS competitionname
                FROM marketcatalogue m
                JOIN eventlist e ON m.eventid = e.id
                JOIN eventtype et ON m.eventtypeid = et.id
                JOIN competition c ON m.competitionid = c.id";

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
                splitOn: "eventid,eventtypeid,competitionid"
            );
    }

    public async Task DisplayMarketBooks(IEnumerable<string> marketIds)
    {
        if (marketIds == null || !marketIds.Any())
        {
            //Console.WriteLine("No market IDs provided.");
            return;
        }

        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        var displayHandler = new DisplayHandler();

        foreach (var marketId in marketIds)
        {
            //Console.WriteLine(new string('*', 215));
            
            const string query = @"
            SELECT 
                mc.marketid, 
                mc.marketname, 
                mc.totalmatched, 
                mc.eventname,
                mbr.id AS backpriceid,
                mbr.selectionid, 
                mbr.status, 
                mbr.lastpricetraded,
                mbr.price AS backprice, 
                mbr.size AS backsize,
                mbl.id AS laypriceid,
                mbl.price AS layprice, 
                mbl.size AS laysize
            FROM 
                marketbookbackprices mbr
            INNER JOIN 
                marketbooklayprices mbl ON mbr.id = mbl.id
            INNER JOIN 
                marketcatalogue mc ON mc.marketid = mbr.marketid
            WHERE 
                mc.marketid = @marketid";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketid", marketId);

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