using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using System.Threading.Tasks;
using Npgsql;
using Dapper;

namespace Betfair.Controllers;

[ApiController]
[Route("api/[controller]")]
public class GreyhoundMarketBookController : ControllerBase
{
    private readonly MarketBookDb _marketBookDb;
    private readonly string _connectionString;

    public GreyhoundMarketBookController(MarketBookDb marketBookDb, IConfiguration configuration)
    {
        _marketBookDb = marketBookDb;
        _connectionString = configuration.GetConnectionString("DefaultDb");
    }

    [HttpGet("details")]
    public async Task<IActionResult> GetGreyhoundMarketBookDetails()
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT DISTINCT 
                    marketid, 
                    marketname, 
                    selectionid, 
                    status,
                    pricetype,
                    price,
                    size
                FROM greyhoundmarketbook 
                ORDER BY marketid, selectionid, pricetype, price";

            var greyhoundMarketBooks = await connection.QueryAsync(query);
            return Ok(greyhoundMarketBooks);
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = "Error fetching greyhound market book details", error = ex.Message });
        }
    }

    [HttpGet("odds/{selectionId}")]
    public async Task<IActionResult> GetGreyhoundBackAndLayOdds(long selectionId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get greyhound details from greyhoundmarketbook
            var greyhoundQuery = @"
                SELECT marketid, marketname, selectionid, status
                FROM greyhoundmarketbook 
                WHERE selectionid = @SelectionId 
                LIMIT 1";

            var greyhoundInfo = await connection.QueryFirstOrDefaultAsync(greyhoundQuery, new { SelectionId = selectionId });

            if (greyhoundInfo == null)
            {
                return NotFound(new { message = $"Greyhound with SelectionId {selectionId} not found" });
            }

            // Get back odds
            var backOddsQuery = @"
                SELECT price, size, marketid
                FROM greyhoundmarketbook 
                WHERE selectionid = @SelectionId 
                AND pricetype = 'AvailableToBack'
                ORDER BY price DESC";

            var backOdds = await connection.QueryAsync(backOddsQuery, new { SelectionId = selectionId });

            // Get lay odds
            var layOddsQuery = @"
                SELECT price, size, marketid
                FROM greyhoundmarketbook 
                WHERE selectionid = @SelectionId 
                AND pricetype = 'AvailableToLay'
                ORDER BY price ASC";

            var layOdds = await connection.QueryAsync(layOddsQuery, new { SelectionId = selectionId });

            return Ok(new
            {
                Greyhound = new
                {
                    SelectionId = selectionId,
                    MarketId = greyhoundInfo.marketid,
                    MarketName = greyhoundInfo.marketname,
                    Status = greyhoundInfo.status
                },
                BackOdds = backOdds.Select(b => new { Price = b.price, Size = b.size, MarketId = b.marketid }),
                LayOdds = layOdds.Select(l => new { Price = l.price, Size = l.size, MarketId = l.marketid })
            });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = "Error fetching greyhound odds", error = ex.Message });
        }
    }

    [HttpGet("market/{marketId}")]
    public async Task<IActionResult> GetGreyhoundMarketOdds(string marketId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT 
                    selectionid,
                    status,
                    pricetype,
                    price,
                    size
                FROM greyhoundmarketbook 
                WHERE marketid = @MarketId
                ORDER BY selectionid, pricetype, price";

            var marketOdds = await connection.QueryAsync(query, new { MarketId = marketId });

            return Ok(new
            {
                marketId,
                odds = marketOdds,
                count = marketOdds.Count(),
                retrievedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = "Error fetching greyhound market odds", error = ex.Message });
        }
    }
}
