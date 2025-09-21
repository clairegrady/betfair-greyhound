using Microsoft.AspNetCore.Mvc;
using Betfair.Services;

namespace Betfair.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class StreamApiController : ControllerBase
    {
        private readonly IStreamApiService _streamApiService;
        private readonly ILogger<StreamApiController> _logger;

        public StreamApiController(
            IStreamApiService streamApiService,
            ILogger<StreamApiController> logger)
        {
            _streamApiService = streamApiService;
            _logger = logger;
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
    }
}
