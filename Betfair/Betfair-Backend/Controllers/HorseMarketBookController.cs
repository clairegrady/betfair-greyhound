using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using Betfair.Services;
using System.Threading.Tasks;

namespace Betfair.Controllers;

[ApiController]
[Route("api/horse-racing")]
public class HorseMarketBookController : ControllerBase
{
    private readonly MarketBookDb _marketBookDb;
    private readonly IMarketApiService _marketApiService;

    public HorseMarketBookController(MarketBookDb marketBookDb, IMarketApiService marketApiService)
    {
        _marketBookDb = marketBookDb;
        _marketApiService = marketApiService;
    }

    [HttpGet("details")]
    public async Task<IActionResult> GetHorseMarketBookDetails()
    {
        var horseMarketBooks = await _marketBookDb.GetHorseMarketBooksAsync();
        foreach (var horseMarketBook in horseMarketBooks)
        {
            Console.WriteLine("***" + horseMarketBook);
        }

        return Ok(horseMarketBooks);
    }

    [HttpGet("odds/{selectionId}")]
    public async Task<IActionResult> GetHorseBackAndLayOdds(long selectionId)
    {
        var oddsData = await _marketBookDb.GetHorseBackAndLayOddsAsync(selectionId);
        return Ok(oddsData);
    }

    [HttpGet("market-book/{marketId}")]
    public async Task<IActionResult> GetMarketBook(string marketId)
    {
        try
        {
            Console.WriteLine($"Fetching market book for market ID: {marketId}");
            
            // Call Betfair API to get market book
            var jsonResponse = await _marketApiService.ListMarketBookAsync(new List<string> { marketId });
            
            if (string.IsNullOrEmpty(jsonResponse))
            {
                Console.WriteLine($"Empty response for market {marketId}");
                return NotFound(new { error = $"Market {marketId} not found" });
            }

            // Parse and return the first market book
            var response = System.Text.Json.JsonSerializer.Deserialize<System.Text.Json.JsonElement>(jsonResponse);
            
            if (response.TryGetProperty("result", out var result) && result.GetArrayLength() > 0)
            {
                var marketBook = result[0];
                Console.WriteLine($"Successfully fetched market book for {marketId}");
                return Ok(marketBook);
            }

            Console.WriteLine($"No data in result for market {marketId}");
            return NotFound(new { error = $"No data for market {marketId}" });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"ERROR in GetMarketBook for {marketId}: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");
            return StatusCode(500, new { error = ex.Message, details = ex.StackTrace });
        }
    }
}
