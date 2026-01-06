using Microsoft.AspNetCore.Mvc;
using Betfair.Services;

namespace Betfair.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ResultsController : ControllerBase
    {
        private readonly IResultsService _resultsService;
        private readonly ILogger<ResultsController> _logger;

        public ResultsController(IResultsService resultsService, ILogger<ResultsController> logger)
        {
            _resultsService = resultsService;
            _logger = logger;
        }

        [HttpPost("settled")]
        public async Task<IActionResult> GetSettledMarkets([FromBody] SettledMarketsRequest request)
        {
            try
            {
                if (request?.MarketIds == null || !request.MarketIds.Any())
                {
                    return BadRequest(new { message = "Market IDs are required" });
                }

                _logger.LogInformation("🏁 Fetching settled results for {Count} markets", request.MarketIds.Count);
                
                var markets = await _resultsService.GetSettledMarketsAsync(request.MarketIds);
                
                return Ok(new
                {
                    markets = markets,
                    fetched_at = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "❌ Error fetching settled markets");
                return StatusCode(500, new { error = ex.Message });
            }
        }

        [HttpPost("catalogue")]
        public async Task<IActionResult> GetMarketCatalogue([FromBody] SettledMarketsRequest request)
        {
            try
            {
                if (request?.MarketIds == null || !request.MarketIds.Any())
                {
                    return BadRequest(new { message = "Market IDs are required" });
                }

                _logger.LogInformation("📋 Fetching market catalogue for {Count} markets", request.MarketIds.Count);
                
                var markets = await _resultsService.GetMarketCatalogueAsync(request.MarketIds);
                
                return Ok(new
                {
                    markets = markets,
                    fetched_at = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "❌ Error fetching market catalogue");
                return StatusCode(500, new { error = ex.Message });
            }
        }
    }

    public class SettledMarketsRequest
    {
        public List<string> MarketIds { get; set; } = new();
    }
}
