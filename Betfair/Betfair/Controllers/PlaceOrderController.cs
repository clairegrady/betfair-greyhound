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

    /// <summary>
    /// Place a bet with ML-enhanced decision making for place bets only
    /// </summary>
    [HttpPost("ml-place-bet")]
    public async Task<IActionResult> PlaceMLBet([FromBody] MLPlaceOrderRequest request)
    {
        if (request == null)
            return BadRequest("Invalid request body.");

        _logger.LogInformation("🤖 ML Place Bet Request: Market {MarketId}, Selection {SelectionId}, Stake {Stake}", 
            request.MarketId, request.SelectionId, request.Stake);

        try
        {
            // Get ML predictions
            var predictions = await _mlPredictionService.GetRacePredictionsAsync(request.MarketId);
            if (predictions == null)
            {
                return BadRequest(new MLPlaceOrderResponse
                {
                    BetPlaced = false,
                    Reason = "Unable to get ML predictions - API unavailable",
                    MLConfidence = 0
                });
            }

            // Find the horse prediction
            var horsePrediction = predictions.Predictions
                .FirstOrDefault(p => p.SelectionId == request.SelectionId.ToString());

            if (horsePrediction == null)
            {
                return BadRequest(new MLPlaceOrderResponse
                {
                    BetPlaced = false,
                    Reason = "Horse not found in ML predictions",
                    MLConfidence = 0
                });
            }

            // Check if we should place the bet
            bool shouldBet = request.ForcePlace || 
                await _mlPredictionService.ShouldPlaceBetAsync(request.MarketId, request.SelectionId, request.MinConfidence);

            var response = new MLPlaceOrderResponse
            {
                MLConfidence = horsePrediction.PlaceProbability,
                HorseName = horsePrediction.HorseName,
                MarketPosition = horsePrediction.MarketPosition,
                OddsUsed = (decimal?)horsePrediction.BettingOdds.LowestBackPrice
            };

            if (!shouldBet)
            {
                response.BetPlaced = false;
                response.Reason = $"ML analysis recommends against betting (Confidence: {horsePrediction.PlaceProbability:P1} < {request.MinConfidence:P1})";
                
                _logger.LogInformation("❌ ML Bet Rejected: {Reason}", response.Reason);
                return Ok(response);
            }

            // Check odds constraints
            if (request.MaxOdds.HasValue && horsePrediction.BettingOdds.LowestBackPrice > (double)request.MaxOdds)
            {
                response.BetPlaced = false;
                response.Reason = $"Odds too high ({horsePrediction.BettingOdds.LowestBackPrice} > {request.MaxOdds})";
                
                _logger.LogInformation("❌ ML Bet Rejected: {Reason}", response.Reason);
                return Ok(response);
            }

            // Place the bet using existing service
            var placeOrderRequest = new PlaceOrderRequest
            {
                MarketId = request.MarketId,
                SelectionId = request.SelectionId,
                Stake = request.Stake,
                // Add other required fields based on your PlaceOrderRequest model
            };

            var betResult = await _placeOrderService.PlaceOrdersAsync(placeOrderRequest);
            
            response.BetPlaced = true;
            response.Reason = $"ML analysis supports betting (Confidence: {horsePrediction.PlaceProbability:P1})";
            response.BetfairResult = betResult;

            _logger.LogInformation("✅ ML Bet Placed: {HorseName} at {Confidence:P1} confidence", 
                horsePrediction.HorseName, horsePrediction.PlaceProbability);

            return Ok(response);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error processing ML place bet");
            return StatusCode(500, new MLPlaceOrderResponse
            {
                BetPlaced = false,
                Reason = $"Error processing ML bet: {ex.Message}",
                MLConfidence = 0
            });
        }
    }

    /// <summary>
    /// Get ML predictions for a race without placing bets
    /// </summary>
    [HttpGet("predictions/{marketId}")]
    public async Task<IActionResult> GetMLPredictions(string marketId)
    {
        try
        {
            var predictions = await _mlPredictionService.GetRacePredictionsAsync(marketId);
            if (predictions == null)
            {
                return NotFound($"No ML predictions available for market {marketId}");
            }

            return Ok(predictions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error getting ML predictions for market {MarketId}", marketId);
            return StatusCode(500, $"Error getting predictions: {ex.Message}");
        }
    }

    /// <summary>
    /// Get betting recommendations for a race
    /// </summary>
    [HttpGet("recommendations/{marketId}")]
    public async Task<IActionResult> GetBettingRecommendations(string marketId)
    {
        try
        {
            var recommendations = await _mlPredictionService.GetBettingRecommendationsAsync(marketId);
            return Ok(recommendations);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error getting betting recommendations for market {MarketId}", marketId);
            return StatusCode(500, $"Error getting recommendations: {ex.Message}");
        }
    }

}