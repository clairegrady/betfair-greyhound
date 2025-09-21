using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.Sqlite;
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
    private readonly string _bettingHistoryConnectionString;
    private readonly ILogger<OddsController> _logger;
    private readonly IMarketApiService _marketApiService;

    public OddsController(IConfiguration configuration, ILogger<OddsController> logger, IMarketApiService marketApiService)
    {
        _connectionString = configuration.GetConnectionString("DefaultDb");
        _bettingHistoryConnectionString = configuration.GetConnectionString("BettingHistoryDb");
        _logger = logger;
        _marketApiService = marketApiService;
    }

    [HttpGet("current/{marketId}/{selectionId}")]
    public async Task<IActionResult> GetCurrentOdds(string marketId, int selectionId)
    {
        try
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            // Get current best lay price
            var query = @"
                SELECT MIN(Price) as best_lay_price, COUNT(*) as price_count
                FROM MarketBookLayPrices 
                WHERE MarketId = @marketId 
                AND SelectionId = @selectionId 
                AND Price > 0 
                AND Status = 'ACTIVE'";

            using var command = new SqliteCommand(query, connection);
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
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            // Get all active lay prices for the market
            var query = @"
                SELECT m.SelectionId, h.RUNNER_NAME, h.CLOTH_NUMBER, 
                       MIN(m.Price) as best_lay_price, COUNT(*) as price_count
                FROM MarketBookLayPrices m
                JOIN HorseMarketBook h ON m.SelectionId = h.SelectionId
                WHERE m.MarketId = @marketId 
                AND m.Price > 0 
                AND m.Status = 'ACTIVE'
                GROUP BY m.SelectionId, h.RUNNER_NAME, h.CLOTH_NUMBER
                ORDER BY h.CLOTH_NUMBER";

            using var command = new SqliteCommand(query, connection);
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

    [HttpGet("refresh/{marketId}")]
    public async Task<IActionResult> RefreshOdds(string marketId)
    {
        try
        {
            _logger.LogInformation("Refreshing odds for market {MarketId}", marketId);
            
            // Fetch fresh odds from Betfair API with timeout
            var marketIds = new List<string> { marketId };
            var response = await _marketApiService.ListMarketBookAsync(marketIds);
            
            // Parse the response using existing logic
            ApiResponse<MarketBook<ApiRunner>> marketBookResponse;
            try
            {
                marketBookResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(response);
            }
            catch (JsonException ex)
            {
                _logger.LogError($"JSON deserialization error for market {marketId}: {ex.Message}");
                _logger.LogError($"Response content: {response}");
                return StatusCode(500, new { message = "Failed to parse market data", details = ex.Message });
            }
            
            if (marketBookResponse?.Result == null || !marketBookResponse.Result.Any())
            {
                return NotFound(new { message = "No market data found" });
            }
            
            // Update the betting_history database with fresh odds data
            using var connection = new SqliteConnection(_bettingHistoryConnectionString);
            await connection.OpenAsync();
            
            using var transaction = await connection.BeginTransactionAsync();
            
            // Clear existing odds for this market
            var clearQuery = "DELETE FROM CurrentOdds WHERE MarketId = @marketId";
            using var clearCommand = new SqliteCommand(clearQuery, connection);
            clearCommand.Transaction = (SqliteTransaction)transaction;
            clearCommand.Parameters.AddWithValue("@marketId", marketId);
            await clearCommand.ExecuteNonQueryAsync();
            
            // Clear existing BSP projections for this market
            var clearBspQuery = "DELETE FROM BSPProjections WHERE MarketId = @marketId";
            using var clearBspCommand = new SqliteCommand(clearBspQuery, connection);
            clearBspCommand.Transaction = (SqliteTransaction)transaction;
            clearBspCommand.Parameters.AddWithValue("@marketId", marketId);
            await clearBspCommand.ExecuteNonQueryAsync();
            
            int totalLayPrices = 0;
            
            // Insert fresh odds data into CurrentOdds table
            foreach (var marketBook in marketBookResponse.Result)
            {
                foreach (var runner in marketBook.Runners)
                {
                    if (runner.Exchange?.AvailableToLay != null)
                    {
                        foreach (var lay in runner.Exchange.AvailableToLay)
                        {
                            var insertQuery = @"
                                INSERT INTO CurrentOdds
                                (MarketId, SelectionId, RunnerName, Price, Size, Status, LastPriceTraded, TotalMatched, UpdatedAt)
                                VALUES
                                ($MarketId, $SelectionId, $RunnerName, $Price, $Size, $Status, $LastPriceTraded, $TotalMatched, $UpdatedAt)";
                            
                            using var priceCommand = new SqliteCommand(insertQuery, connection);
                            priceCommand.Transaction = (SqliteTransaction)transaction;

                            priceCommand.Parameters.AddWithValue("$MarketId", marketId);
                            priceCommand.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                            priceCommand.Parameters.AddWithValue("$RunnerName", runner.Description?.RunnerName ?? $"Horse {runner.SelectionId}");
                            priceCommand.Parameters.AddWithValue("$Price", (double)lay.Price);
                            priceCommand.Parameters.AddWithValue("$Size", (double)lay.Size);
                            priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$UpdatedAt", DateTime.UtcNow);

                            await priceCommand.ExecuteNonQueryAsync();
                            totalLayPrices++;
                        }
                    }
                }
            }
            
            // Insert BSP projections into BSPProjections table
            int totalBspProjections = 0;
            foreach (var marketBook in marketBookResponse.Result)
            {
                foreach (var runner in marketBook.Runners)
                {
                    if (runner.Sp?.NearPrice != null || runner.Sp?.FarPrice != null)
                    {
                        var bspInsertQuery = @"
                            INSERT OR REPLACE INTO BSPProjections
                            (MarketId, SelectionId, RunnerName, NearPrice, FarPrice, Average, UpdatedAt)
                            VALUES
                            ($MarketId, $SelectionId, $RunnerName, $NearPrice, $FarPrice, $Average, $UpdatedAt)";
                        
                        using var bspCommand = new SqliteCommand(bspInsertQuery, connection);
                        bspCommand.Transaction = (SqliteTransaction)transaction;
                        
                        bspCommand.Parameters.AddWithValue("$MarketId", marketId);
                        bspCommand.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                        bspCommand.Parameters.AddWithValue("$RunnerName", runner.Description?.RunnerName ?? $"Horse {runner.SelectionId}");
                        bspCommand.Parameters.AddWithValue("$NearPrice", runner.Sp?.NearPrice ?? (object)DBNull.Value);
                        bspCommand.Parameters.AddWithValue("$FarPrice", runner.Sp?.FarPrice ?? (object)DBNull.Value);
                        
                        var nearPrice = runner.Sp?.NearPrice;
                        var farPrice = runner.Sp?.FarPrice;
                        var average = (nearPrice != null && farPrice != null) 
                            ? (nearPrice + farPrice) / 2.0 
                            : (object)DBNull.Value;
                        bspCommand.Parameters.AddWithValue("$Average", average);
                        bspCommand.Parameters.AddWithValue("$UpdatedAt", DateTime.UtcNow);
                        
                        await bspCommand.ExecuteNonQueryAsync();
                        totalBspProjections++;
                    }
                }
            }
            
            await transaction.CommitAsync();
            
            _logger.LogInformation("Successfully refreshed {Count} lay prices and {BspCount} BSP projections for market {MarketId}", totalLayPrices, totalBspProjections, marketId);
            
            return Ok(new
            {
                marketId,
                message = "Odds refreshed successfully",
                layPricesCount = totalLayPrices,
                refreshedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing odds for market {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error" });
        }
    }
}
