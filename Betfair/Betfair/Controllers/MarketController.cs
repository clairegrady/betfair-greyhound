using Microsoft.AspNetCore.Mvc;
using Betfair.Services;
using System.Text.Json;
using Betfair.Models.Market;

namespace Betfair.Controllers;

[Route("api/[controller]")]
[ApiController]
public class MarketController : ControllerBase
{
    private readonly MarketService _marketService;

    public MarketController(MarketService marketService)
    {
        _marketService = marketService;
    }

    // GET api/market/profit-and-loss
    [HttpGet("profit-and-loss")]
    public async Task<IActionResult> GetProfitAndLoss([FromQuery] List<string> marketIds)
    {
        if (marketIds == null || marketIds.Count == 0)
        {
            return BadRequest("Market IDs are required.");
        }

        try
        {
            var responseJson = await _marketService.GetMarketProfitAndLossAsync(marketIds);

            var result = JsonSerializer.Deserialize<MarketProfitAndLossApiResponse>(responseJson);

            if (result?.Result != null && result.Result.Count > 0)
            {
                return Ok(result);
            }
            else
            {
                return NotFound("No profit and loss data found for the provided market IDs.");
            }
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Internal server error: {ex.Message}");
        }
    }
}