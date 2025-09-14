using Microsoft.AspNetCore.Mvc;
using Betfair.Services;

namespace Betfair.Controllers;

[ApiController]
[Route("api/[controller]")]
public class CompetitionsController : ControllerBase
{
    private readonly ICompetitionService _competitionService;

    public CompetitionsController(ICompetitionService competitionService)
    {
        _competitionService = competitionService;
    }

    [HttpPost("listCompetitions")]
    public async Task<IActionResult> ListCompetitions()
    {
        try
        {
            var result = await _competitionService.FetchAndInsertCompetitionsAsync();

            if (result.IsSuccess)
            {
                return Ok("Competitions inserted into database successfully.");
            }

            return BadRequest(result.ErrorMessage);
        }
        catch (Exception ex)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, "Internal server error");
        }
    }

    [HttpPost("insertCompetitions")]
    public async Task<IActionResult> InsertCompetitions()
    {
        try
        {
            var result = await _competitionService.FetchAndInsertCompetitionsAsync();

            if (result.IsSuccess)
            {
                return Ok("Competitions inserted successfully.");
            }

            return BadRequest(result.ErrorMessage);
        }
        catch (Exception ex)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, "Internal server error");
        }
    }
}
