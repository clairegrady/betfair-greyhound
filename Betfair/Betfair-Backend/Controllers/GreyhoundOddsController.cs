using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.Sqlite;
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
    private readonly string _bettingHistoryConnectionString;
    private readonly ILogger<GreyhoundOddsController> _logger;
    private readonly IMarketApiService _marketApiService;

    public GreyhoundOddsController(IConfiguration configuration, ILogger<GreyhoundOddsController> logger, IMarketApiService marketApiService)
    {
        _connectionString = configuration.GetConnectionString("DefaultDb");
        _bettingHistoryConnectionString = configuration.GetConnectionString("BettingHistoryDb");
        _logger = logger;
        _marketApiService = marketApiService;
    }

    [HttpGet("current/{marketId}/{selectionId}")]
    public async Task<IActionResult> GetCurrentGreyhoundOdds(string marketId, int selectionId)
    {
        try
        {
            using var connection = new SqliteConnection(_connectionString);
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
            using var connection = new SqliteConnection(_connectionString);
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

            using var command = new SqliteCommand(query, connection);
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

    [HttpGet("refresh/{marketId}")]
    public async Task<IActionResult> RefreshGreyhoundOdds(string marketId)
    {
        try
        {
            _logger.LogInformation("Refreshing greyhound odds for market {MarketId}", marketId);
            
            // Refresh the greyhound market odds
            await RefreshGreyhoundMarketOdds(marketId, "CurrentGreyhoundWinOdds");
            
            return Ok(new
            {
                marketId,
                message = "Greyhound odds refreshed successfully",
                refreshedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing greyhound odds for market {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error", details = ex.Message });
        }
    }
    
    private async Task<int> RefreshGreyhoundMarketOdds(string marketId, string tableName)
    {
        try
        {
            // Fetch fresh odds from Betfair API
            var marketIds = new List<string> { marketId };
            var response = await _marketApiService.ListMarketBookAsync(marketIds);
            
            // Parse the response
            ApiResponse<MarketBook<ApiRunner>> marketBookResponse;
            try
            {
                marketBookResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(response);
            }
            catch (JsonException ex)
            {
                _logger.LogError($"JSON deserialization error for greyhound market {marketId}: {ex.Message}");
                return 0;
            }
            
            if (marketBookResponse?.Result == null || !marketBookResponse.Result.Any())
            {
                return 0;
            }
            
            // Update the betting_history database with fresh greyhound odds data
            using var connection = new SqliteConnection(_bettingHistoryConnectionString);
            await connection.OpenAsync();
            
            using var transaction = await connection.BeginTransactionAsync();
            
            // Clear existing odds for this market
            var clearQuery = $"DELETE FROM {tableName} WHERE MarketId = @marketId";
            using var clearCommand = new SqliteCommand(clearQuery, connection);
            clearCommand.Transaction = (SqliteTransaction)transaction;
            clearCommand.Parameters.AddWithValue("@marketId", marketId);
            await clearCommand.ExecuteNonQueryAsync();
            
            int totalOddsRecords = 0;
            
            // Insert fresh greyhound odds data
            foreach (var marketBook in marketBookResponse.Result)
            {
                foreach (var runner in marketBook.Runners)
                {
                    // Get best back odds
                    double? bestBackPrice = null;
                    double? bestBackSize = null;
                    if (runner.Exchange?.AvailableToBack != null && runner.Exchange.AvailableToBack.Any())
                    {
                        var bestBack = runner.Exchange.AvailableToBack.OrderByDescending(b => b.Price).First();
                        bestBackPrice = (double)bestBack.Price;
                        bestBackSize = (double)bestBack.Size;
                    }
                    
                    // Get best lay odds
                    double? bestLayPrice = null;
                    double? bestLaySize = null;
                    if (runner.Exchange?.AvailableToLay != null && runner.Exchange.AvailableToLay.Any())
                    {
                        var bestLay = runner.Exchange.AvailableToLay.OrderBy(l => l.Price).First();
                        bestLayPrice = (double)bestLay.Price;
                        bestLaySize = (double)bestLay.Size;
                    }
                    
                    // Only insert if we have at least back or lay odds
                    if (bestBackPrice.HasValue || bestLayPrice.HasValue)
                    {
                        var insertQuery = $@"
                            INSERT INTO {tableName}
                            (MarketId, SelectionId, RunnerName, Price, Size, Status, LastPriceTraded, TotalMatched, UpdatedAt, best_back_price, best_lay_price, best_back_size, best_lay_size)
                            VALUES
                            ($MarketId, $SelectionId, $RunnerName, $Price, $Size, $Status, $LastPriceTraded, $TotalMatched, $UpdatedAt, $BestBackPrice, $BestLayPrice, $BestBackSize, $BestLaySize)";
                        
                        using var priceCommand = new SqliteCommand(insertQuery, connection);
                        priceCommand.Transaction = (SqliteTransaction)transaction;

                        priceCommand.Parameters.AddWithValue("$MarketId", marketId);
                        priceCommand.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                        priceCommand.Parameters.AddWithValue("$RunnerName", runner.Description?.RunnerName ?? $"Greyhound {runner.SelectionId}");
                        priceCommand.Parameters.AddWithValue("$Price", bestBackPrice ?? bestLayPrice ?? 0);
                        priceCommand.Parameters.AddWithValue("$Size", bestBackSize ?? bestLaySize ?? 0);
                        priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$UpdatedAt", DateTime.UtcNow);
                        priceCommand.Parameters.AddWithValue("$BestBackPrice", bestBackPrice ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$BestLayPrice", bestLayPrice ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$BestBackSize", bestBackSize ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$BestLaySize", bestLaySize ?? (object)DBNull.Value);

                        await priceCommand.ExecuteNonQueryAsync();
                        totalOddsRecords++;
                    }
                }
            }
            
            await transaction.CommitAsync();
            
            _logger.LogInformation("Successfully refreshed {Count} greyhound odds records for market {MarketId} in table {TableName}", totalOddsRecords, marketId, tableName);
            
            return totalOddsRecords;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing greyhound odds for market {MarketId} in table {TableName}", marketId, tableName);
            return 0;
        }
    }
}
