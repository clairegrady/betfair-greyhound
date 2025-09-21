using Microsoft.AspNetCore.Mvc;
using Betfair.Services.Account;
using Betfair.Models.Account;

namespace Betfair.Controllers;

[Route("api/[controller]")]
[ApiController]
public class ManageOrdersController : ControllerBase
{
    private readonly IPlaceOrderService _placeOrderService;
    private readonly ILogger<ManageOrdersController> _logger;

    public ManageOrdersController(
        IPlaceOrderService placeOrderService,
        ILogger<ManageOrdersController> logger)
    {
        _placeOrderService = placeOrderService;
        _logger = logger;
    }

    // GET: api/manageorders/current
    [HttpGet("current")]
    public async Task<IActionResult> GetCurrentOrders()
    {
        try
        {
            var orders = await _placeOrderService.ListCurrentOrdersAsync();
            return Ok(orders);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching current orders");
            return StatusCode(500, $"Error fetching current orders: {ex.Message}");
        }
    }

    // POST: api/manageorders/cancel
    [HttpPost("cancel")]
    public async Task<IActionResult> CancelOrders(string marketId, [FromBody] List<CancelInstruction> instructions, string customerRef = null)
    {
        if (instructions == null || instructions.Count == 0)
            return BadRequest("No cancel instructions provided.");

        try
        {
            var result = await _placeOrderService.CancelOrderAsync(marketId, instructions, customerRef);
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error cancelling orders");
            return StatusCode(500, $"Error cancelling orders: {ex.Message}");
        }
    }

    // POST: api/manageorders/update
    [HttpPost("update")]
    public async Task<IActionResult> UpdateOrders(string marketId, [FromBody] List<UpdateInstruction> instructions, string customerRef = null)
    {
        if (instructions == null || instructions.Count == 0)
            return BadRequest("No update instructions provided.");

        try
        {
            var result = await _placeOrderService.UpdateOrdersAsync(marketId, instructions, customerRef);
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error updating orders");
            return StatusCode(500, $"Error updating orders: {ex.Message}");
        }
    }

    [HttpPost("replace")]
    public async Task<IActionResult> ReplaceOrders([FromBody] ReplaceOrdersRequest request)
    {
        try
        {
            var result = await _placeOrderService.ReplaceOrdersAsync(
                request.MarketId,
                request.Instructions,
                request.CustomerRef,
                request.MarketVersion,
                request.Async
            );

            return Ok(result);
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Error replacing orders: {ex.Message}");
        }
    }
}
