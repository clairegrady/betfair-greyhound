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

            // Get all active lay prices for the greyhound market
            var query = @"
                SELECT 
                    SelectionId,
                    MIN(CASE WHEN PriceType = 'AvailableToLay' THEN Price END) as best_lay_price,
                    MIN(CASE WHEN PriceType = 'AvailableToBack' THEN Price END) as best_back_price,
                    COUNT(*) as price_count
                FROM GreyhoundMarketBook
                WHERE MarketId = @marketId 
                AND Price > 0 
                AND Status = 'ACTIVE'
                GROUP BY SelectionId
                ORDER BY SelectionId";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            var odds = new List<object>();
            while (await reader.ReadAsync())
            {
                odds.Add(new
                {
                    selectionId = reader.GetInt32(0),
                    bestLayPrice = reader.IsDBNull(1) ? (double?)null : reader.GetDouble(1),
                    bestBackPrice = reader.IsDBNull(2) ? (double?)null : reader.GetDouble(2),
                    priceCount = reader.GetInt32(3)
                });
            }

            return Ok(new
            {
                marketId,
                odds,
                count = odds.Count,
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
