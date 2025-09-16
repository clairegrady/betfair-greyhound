using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using System.Threading.Tasks;

namespace Betfair.Controllers;

[ApiController]
[Route("api/[controller]")]
public class HorseMarketBookController : ControllerBase
{
    private readonly MarketBookDb _marketBookDb;

    public HorseMarketBookController(MarketBookDb marketBookDb)
    {
        _marketBookDb = marketBookDb;
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
}
