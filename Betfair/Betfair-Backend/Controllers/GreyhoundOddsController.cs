using Microsoft.AspNetCore.Mvc;
using Npgsql;
using Betfair.Services;
using System.Text.Json;
using Betfair.Models;
using Betfair.Models.Runner;
using Betfair.Models.Market;

namespace Betfair.Controllers;

[Route("api/[controller]")]
[ApiController]
public class GreyhoundOddsController : ControllerBase
{
    private readonly string _connectionString;
    private readonly ILogger<GreyhoundOddsController> _logger;

    public GreyhoundOddsController(IConfiguration configuration, ILogger<GreyhoundOddsController> logger)
    {
        _connectionString = configuration.GetConnectionString("DefaultDb");
        _logger = logger;
    }

    [HttpGet("current/{marketId}/{selectionId}")]
    public async Task<IActionResult> GetCurrentGreyhoundOdds(string marketId, int selectionId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get current best lay price for greyhounds
            var query = @"
                SELECT MIN(Price) as best_lay_price, COUNT(*) as price_count
                FROM GreyhoundMarketBook 
                WHERE MarketId = @marketId 
                AND SelectionId = @selectionId 
                AND Price > 0 
                AND Status = 'ACTIVE'
                AND PriceType = 'AvailableToLay'";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);
            command.Parameters.AddWithValue("@selectionId", selectionId);

            using var reader = await command.ExecuteReaderAsync();
            
            if (await reader.ReadAsync())
            {
                var bestLayPrice = reader.IsDBNull(0) ? (double?)null : reader.GetDouble(0);
                var priceCount = reader.GetInt32(1);

                return Ok(new
                {
                    marketId,
                    selectionId,
                    bestLayPrice,
                    priceCount,
                    hasActivePrices = priceCount > 0
                });
            }

            return NotFound(new { message = "No active greyhound prices found" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting current greyhound odds for market {MarketId}, selection {SelectionId}", marketId, selectionId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }

    [HttpGet("market/{marketId}")]
    public async Task<IActionResult> GetGreyhoundMarketOdds(string marketId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get all active lay prices for the greyhound market WITH runner names and box numbers
            var query = @"
                SELECT 
                    gmb.selectionid,
                    MIN(CASE WHEN gmb.pricetype = 'AvailableToLay' THEN gmb.price END) as best_lay_price,
                    MIN(CASE WHEN gmb.pricetype = 'AvailableToBack' THEN gmb.price END) as best_back_price,
                    COUNT(*) as price_count,
                    mcr.runnername,
                    mcr.sortpriority as box
                FROM greyhoundmarketbook gmb
                LEFT JOIN marketcatalogue_runners mcr 
                    ON gmb.marketid = mcr.marketid 
                    AND gmb.selectionid = mcr.selectionid
                WHERE gmb.marketid = @marketId 
                AND gmb.price > 0 
                AND gmb.status = 'ACTIVE'
                GROUP BY gmb.selectionid, mcr.runnername, mcr.sortpriority
                ORDER BY gmb.selectionid";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            var runners = new List<object>();
            while (await reader.ReadAsync())
            {
                var selectionId = reader.GetInt32(0);
                var runnerName = reader.IsDBNull(4) ? $"Runner {selectionId}" : reader.GetString(4);
                var box = reader.IsDBNull(5) ? (int?)null : reader.GetInt32(5);
                
                runners.Add(new
                {
                    selectionId,
                    runnerName,
                    box,
                    ex = new
                    {
                        availableToLay = reader.IsDBNull(1) ? new List<object>() : new List<object>
                        {
                            new { price = reader.GetDouble(1), size = 0.0 }
                        },
                        availableToBack = reader.IsDBNull(2) ? new List<object>() : new List<object>
                        {
                            new { price = reader.GetDouble(2), size = 0.0 }
                        }
                    }
                });
            }

            return Ok(new
            {
                marketId,
                runners,  // For LIVE script
                odds = runners,  // For simulated scripts (compatibility)
                count = runners.Count,
                retrievedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting greyhound market odds for {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }
}
