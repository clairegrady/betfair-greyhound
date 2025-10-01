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
            
            // First refresh the win market odds
            await RefreshMarketOdds(marketId, "CurrentWinOdds");
            
            // Then refresh the place market odds (market ID + 0.000000001)
            decimal currentId = decimal.Parse(marketId);
            decimal placeMarketId = currentId + 0.000000001m;
            string placeMarketIdStr = placeMarketId.ToString("F9");
            
            _logger.LogInformation("Refreshing place odds for market {PlaceMarketId}", placeMarketIdStr);
            await RefreshMarketOdds(placeMarketIdStr, "CurrentPlaceOdds");
            
            return Ok(new
            {
                marketId,
                message = "Odds refreshed successfully",
                oddsRecordsCount = 0, // We'll calculate this in the helper method
                bspProjectionsCount = 0,
                refreshedAt = DateTime.UtcNow
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing odds for market {MarketId}", marketId);
            return StatusCode(500, new { message = "Internal server error", details = ex.Message });
        }
    }
    
    private async Task<int> RefreshMarketOdds(string marketId, string tableName)
    {
        try
        {
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
                return 0;
            }
            
            if (marketBookResponse?.Result == null || !marketBookResponse.Result.Any())
            {
                return 0;
            }
            
            // Update the betting_history database with fresh odds data
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
            
            // Insert fresh odds data into the specified table with best back and lay odds
            foreach (var marketBook in marketBookResponse.Result)
            {
                foreach (var runner in marketBook.Runners)
                {
                    // Get best back odds (highest price)
                    double? bestBackPrice = null;
                    double? bestBackSize = null;
                    if (runner.Exchange?.AvailableToBack != null && runner.Exchange.AvailableToBack.Any())
                    {
                        var bestBack = runner.Exchange.AvailableToBack.OrderByDescending(b => b.Price).First();
                        bestBackPrice = (double)bestBack.Price;
                        bestBackSize = (double)bestBack.Size;
                    }
                    
                    // Get best lay odds (lowest price)
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
                        priceCommand.Parameters.AddWithValue("$RunnerName", runner.Description?.RunnerName ?? $"Horse {runner.SelectionId}");
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
            
            _logger.LogInformation("Successfully refreshed {Count} odds records for market {MarketId} in table {TableName}", totalOddsRecords, marketId, tableName);
            
            return totalOddsRecords;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing odds for market {MarketId} in table {TableName}", marketId, tableName);
            return 0;
        }
    }

    [HttpGet("bsp/{marketId}")]
    public async Task<IActionResult> GetBspProjections(string marketId)
    {
        try
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            var query = @"
                SELECT MarketId, SelectionId, RunnerName, NearPrice, FarPrice, Average, UpdatedAt
                FROM BSPProjections 
                WHERE MarketId = @marketId
                ORDER BY SelectionId";

            using var command = new SqliteCommand(query, connection);
            command.Parameters.AddWithValue("@marketId", marketId);

            using var reader = await command.ExecuteReaderAsync();
            
            var bspProjections = new List<object>();
            while (await reader.ReadAsync())
            {
                bspProjections.Add(new
                {
                    marketId = reader["MarketId"].ToString(),
                    selectionId = Convert.ToInt32(reader["SelectionId"]),
                    runnerName = reader["RunnerName"].ToString(),
                    nearPrice = reader["NearPrice"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["NearPrice"]),
                    farPrice = reader["FarPrice"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["FarPrice"]),
                    average = reader["Average"] == DBNull.Value ? (double?)null : Convert.ToDouble(reader["Average"]),
                    updatedAt = Convert.ToDateTime(reader["UpdatedAt"])
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
