using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using Betfair.Services;
using System.Threading.Tasks;
using System.Text.Json;
using Npgsql;
using Dapper;

namespace Betfair.Controllers;

[ApiController]
[Route("api/[controller]")]
public class GreyhoundMarketBookController : ControllerBase
{
    private readonly MarketBookDb _marketBookDb;
    private readonly IMarketApiService _marketApiService;
    private readonly string _connectionString;

    public GreyhoundMarketBookController(
        MarketBookDb marketBookDb, 
        IMarketApiService marketApiService,
        IConfiguration configuration)
    {
        _marketBookDb = marketBookDb;
        _marketApiService = marketApiService;
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

    [HttpGet("status/{marketId}")]
    public async Task<IActionResult> GetMarketStatus(string marketId)
    {
        try
        {
            // Call Betfair's listMarketBook API to get LIVE market status
            var marketBookJson = await _marketApiService.ListMarketBookAsync(new List<string> { marketId });
            
            using var jsonDoc = JsonDocument.Parse(marketBookJson);
            var result = jsonDoc.RootElement.GetProperty("result");
            
            if (result.GetArrayLength() == 0)
            {
                return NotFound(new { 
                    marketId,
                    status = "NOT_FOUND",
                    message = "Market not found or not yet available"
                });
            }
            
            var marketBook = result[0];
            var status = marketBook.GetProperty("status").GetString(); // OPEN, SUSPENDED, CLOSED
            var inplay = marketBook.GetProperty("inplay").GetBoolean();
            var betDelay = marketBook.TryGetProperty("betDelay", out var bd) ? bd.GetInt32() : 0;
            var numberOfActiveRunners = marketBook.TryGetProperty("numberOfActiveRunners", out var nar) ? nar.GetInt32() : 0;
            
            return Ok(new
            {
                marketId,
                status,  // OPEN, SUSPENDED, CLOSED
                inplay,
                betDelay,
                numberOfActiveRunners,
                retrievedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = "Error fetching market status", error = ex.Message });
        }
    }
}
