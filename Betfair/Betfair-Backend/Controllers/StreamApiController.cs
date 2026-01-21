using Microsoft.AspNetCore.Mvc;
using Betfair.Services;
using Npgsql;

namespace Betfair.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class StreamApiController : ControllerBase
    {
        private readonly IStreamApiService _streamApiService;
        private readonly ILogger<StreamApiController> _logger;
        private readonly string _connectionString;

        public StreamApiController(
            IStreamApiService streamApiService,
            ILogger<StreamApiController> logger,
            IConfiguration configuration)
        {
            _streamApiService = streamApiService;
            _logger = logger;
            _connectionString = configuration.GetConnectionString("DefaultDb");
        }

        [HttpGet("status")]
        public IActionResult GetStatus()
        {
            return Ok(new
            {
                IsConnected = _streamApiService.IsConnected,
                IsAuthenticated = _streamApiService.IsAuthenticated,
                Timestamp = DateTime.UtcNow
            });
        }

        [HttpPost("connect")]
        public async Task<IActionResult> Connect()
        {
            try
            {
                var connected = await _streamApiService.ConnectAsync();
                return Ok(new { Success = connected, Message = connected ? "Connected" : "Failed to connect" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error connecting to Stream API");
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }

        [HttpPost("disconnect")]
        public async Task<IActionResult> Disconnect()
        {
            try
            {
                await _streamApiService.DisconnectAsync();
                return Ok(new { Success = true, Message = "Disconnected" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error disconnecting from Stream API");
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }

        [HttpPost("subscribe/market/{marketId}")]
        public async Task<IActionResult> SubscribeToMarket(string marketId)
        {
            try
            {
                await _streamApiService.SubscribeToMarketAsync(marketId);
                return Ok(new { Success = true, Message = $"Subscribed to market {marketId}" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error subscribing to market {marketId}");
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }

        [HttpPost("unsubscribe/market/{marketId}")]
        public async Task<IActionResult> UnsubscribeFromMarket(string marketId)
        {
            try
            {
                await _streamApiService.UnsubscribeFromMarketAsync(marketId);
                return Ok(new { Success = true, Message = $"Unsubscribed from market {marketId}" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error unsubscribing from market {marketId}");
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }

        [HttpPost("heartbeat")]
        public async Task<IActionResult> SendHeartbeat()
        {
            try
            {
                await _streamApiService.SendHeartbeatAsync();
                return Ok(new { Success = true, Message = "Heartbeat sent" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error sending heartbeat");
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }

        [HttpGet("bsp/{marketId}")]
        public async Task<IActionResult> GetBspData(string marketId)
        {
            try
            {
                using var connection = new NpgsqlConnection(_connectionString);
                await connection.OpenAsync();

                var query = @"
                    SELECT MarketId, SelectionId, RunnerName, NearPrice, FarPrice, Average, UpdatedAt
                    FROM StreamBspProjections 
                    WHERE MarketId = @marketId
                    ORDER BY SelectionId";

                using var command = new NpgsqlCommand(query, connection);
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
                    source = "Stream API",
                    retrievedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting Stream API BSP data for market {MarketId}", marketId);
                return BadRequest(new { Success = false, Message = ex.Message });
            }
        }
    }
}
