using Microsoft.AspNetCore.Mvc;
using Npgsql;
using Betfair.Data;
using Betfair.Models.Market;
using Betfair.Services;
using System.Text.Json;
using Betfair.Models;
using Betfair.Models.Runner;

namespace Betfair.Controllers;

[Route("api/[controller]")]
[ApiController]
public class OddsController : ControllerBase
{
    private readonly string _connectionString;
    private readonly ILogger<OddsController> _logger;

    public OddsController(IConfiguration configuration, ILogger<OddsController> logger)
    {
        _connectionString = configuration.GetConnectionString("DefaultDb");
        _logger = logger;
    }

    [HttpGet("current/{marketId}/{selectionId}")]
    public async Task<IActionResult> GetCurrentOdds(string marketId, int selectionId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get current best lay price
            var query = @"
                SELECT MIN(price) as best_lay_price, COUNT(*) as price_count
                FROM marketbooklayprices 
                WHERE marketid = @marketId 
                AND selectionid = @selectionId 
                AND price > 0 
                AND status = 'ACTIVE'";

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

            return NotFound(new { message = "No active prices found" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting current odds for market {MarketId}, selection {SelectionId}", marketId, selectionId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }

    [HttpGet("market/{marketId}")]
    public async Task<IActionResult> GetMarketOdds(string marketId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            // Get all active lay prices for the market
            var query = @"
                SELECT m.selectionid, h.runner_name, h.cloth_number, 
                       MIN(m.price) as best_lay_price, COUNT(*) as price_count
                FROM marketbooklayprices m
                JOIN horsemarketbook h ON m.selectionid = h.selectionid
                WHERE m.marketid = @marketId 
                AND m.price > 0 
                AND m.status = 'ACTIVE'
                GROUP BY m.selectionid, h.runner_name, h.cloth_number
                ORDER BY h.cloth_number";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            var odds = new List<object>();
            while (await reader.ReadAsync())
            {
                odds.Add(new
                {
                    selectionId = reader.GetInt32(0),
                    runnerName = reader.IsDBNull(1) ? null : reader.GetString(1),
                    clothNumber = reader.IsDBNull(2) ? null : reader.GetString(2),
                    bestLayPrice = reader.GetDouble(3),
                    priceCount = reader.GetInt32(4)
                });
            }

            return Ok(new
            {
                marketId,
                odds
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting market odds for {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }

    [HttpGet("bsp/{marketId}")]
    public async Task<IActionResult> GetBspProjections(string marketId)
    {
        try
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT marketid, selectionid, runnername, nearprice, farprice, average, updatedat
                FROM bspprojections 
                WHERE marketid = @marketId
                ORDER BY selectionid";

            using var command = new NpgsqlCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            var bspProjections = new List<object>();
            while (await reader.ReadAsync())
            {
                bspProjections.Add(new
                {
                    marketId = reader["marketid"].ToString(),
                    selectionId = Convert.ToInt32(reader["selectionid"]),
                    runnerName = reader["runnername"].ToString(),
                    nearPrice = reader["nearprice"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["nearprice"]),
                    farPrice = reader["farprice"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["farprice"]),
                    average = reader["average"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["average"]),
                    updatedAt = Convert.ToDateTime(reader["updatedat"])
                });
            }

            return Ok(new
            {
                marketId,
                bspProjections,
                count = bspProjections.Count,
                retrievedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting BSP projections for market {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }
}
