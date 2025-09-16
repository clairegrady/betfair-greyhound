using Microsoft.AspNetCore.Mvc;
using Betfair.Services.Account;
using Betfair.Services.ML;
using Betfair.Models.Account;

namespace Betfair.Controllers;

[Route("api/[controller]")]
[ApiController]
public class PlaceOrderController : ControllerBase
{
    private readonly IPlaceOrderService _placeOrderService;
    private readonly IMLPredictionService _mlPredictionService;
    private readonly ILogger<PlaceOrderController> _logger;

    public PlaceOrderController(
        IPlaceOrderService placeOrderService, 
        IMLPredictionService mlPredictionService,
        ILogger<PlaceOrderController> logger)
    {
        _placeOrderService = placeOrderService;
        _mlPredictionService = mlPredictionService;
        _logger = logger;
    }

    [HttpPost]
    public async Task<IActionResult> PlaceBet([FromBody] PlaceOrderRequest request)
    {
        if (request == null)
            return BadRequest("Invalid request body.");

        try
        {
            var betResult = await _placeOrderService.PlaceOrdersAsync(request);
            return Ok(betResult);
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Error placing bet: {ex.Message}");
        }
    }

}