using Microsoft.AspNetCore.Mvc;
using Betfair.Services;

namespace Betfair.Controllers;

[ApiController]
[Route("api/[controller]")]
public class EventController : ControllerBase
{
    private readonly IEventService _eventService;

    public EventController(IEventService eventService)
    {
        _eventService = eventService;
    }

    [HttpPost("listEventTypes/{eventId}")]
    public async Task<IActionResult> ListEventTypes(int eventId)
    {
        try
        {
            var result = await _eventService.FetchAndInsertEventTypesAsync(eventId);

            if (result.IsSuccess)
            {
                return Ok("Event types inserted into database successfully.");
            }
            return BadRequest(result.ErrorMessage);
        }
        catch (Exception ex)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, "Internal server error");
        }
    }
}