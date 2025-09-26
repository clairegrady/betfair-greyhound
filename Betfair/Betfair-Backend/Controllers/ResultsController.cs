using Microsoft.AspNetCore.Mvc;
using Betfair.Services.Interfaces;

namespace Betfair.Betfair.Backend.Controllers
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
        public async Task<IActionResult> GetSettledMarkets([FromBody] List<string> marketIds)
        {
            try
            {
                if (marketIds == null || !marketIds.Any())
                {
                    return BadRequest(new { message = "Market IDs are required" });
                }

                _logger.LogInformation("Fetching settled results for {Count} markets", marketIds.Count);
                
                var settledMarkets = await _resultsService.GetSettledMarkets(marketIds);
                
                return Ok(new
                {
                    marketIds = marketIds,
                    settledMarkets = settledMarkets,
                    count = settledMarkets.Count,
                    fetchedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching settled markets");
                return StatusCode(500, new { message = "Internal server error", details = ex.Message });
            }
        }
    }
}
