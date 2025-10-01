using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
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
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT DISTINCT 
                    MarketId, 
                    MarketName, 
                    SelectionId, 
                    Status,
                    PriceType,
                    Price,
                    Size
                FROM GreyhoundMarketBook 
                ORDER BY MarketId, SelectionId, PriceType, Price";

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
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            // Get greyhound details from GreyhoundMarketBook
            var greyhoundQuery = @"
                SELECT MarketId, MarketName, SelectionId, Status
                FROM GreyhoundMarketBook 
                WHERE SelectionId = @SelectionId 
                LIMIT 1";

            var greyhoundInfo = await connection.QueryFirstOrDefaultAsync(greyhoundQuery, new { SelectionId = selectionId });

            if (greyhoundInfo == null)
            {
                return NotFound(new { message = $"Greyhound with SelectionId {selectionId} not found" });
            }

            // Get back odds
            var backOddsQuery = @"
                SELECT Price, Size, MarketId
                FROM GreyhoundMarketBook 
                WHERE SelectionId = @SelectionId 
                AND PriceType = 'AvailableToBack'
                ORDER BY Price DESC";

            var backOdds = await connection.QueryAsync(backOddsQuery, new { SelectionId = selectionId });

            // Get lay odds
            var layOddsQuery = @"
                SELECT Price, Size, MarketId
                FROM GreyhoundMarketBook 
                WHERE SelectionId = @SelectionId 
                AND PriceType = 'AvailableToLay'
                ORDER BY Price ASC";

            var layOdds = await connection.QueryAsync(layOddsQuery, new { SelectionId = selectionId });

            return Ok(new
            {
                Greyhound = new
                {
                    SelectionId = selectionId,
                    MarketId = greyhoundInfo.MarketId,
                    MarketName = greyhoundInfo.MarketName,
                    Status = greyhoundInfo.Status
                },
                BackOdds = backOdds.Select(b => new { Price = b.Price, Size = b.Size, MarketId = b.MarketId }),
                LayOdds = layOdds.Select(l => new { Price = l.Price, Size = l.Size, MarketId = l.MarketId })
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
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT 
                    SelectionId,
                    Status,
                    PriceType,
                    Price,
                    Size
                FROM GreyhoundMarketBook 
                WHERE MarketId = @MarketId
                ORDER BY SelectionId, PriceType, Price";

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
