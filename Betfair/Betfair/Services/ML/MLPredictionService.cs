using System.Text.Json;
using Betfair.Models.ML;

namespace Betfair.Services.ML;

/// <summary>
/// Implementation of ML prediction service that calls the Python API
/// </summary>
public class MLPredictionService : IMLPredictionService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<MLPredictionService> _logger;
    private readonly string _apiBaseUrl;

    public MLPredictionService(HttpClient httpClient, ILogger<MLPredictionService> logger, IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _apiBaseUrl = configuration.GetValue<string>("MLApi:BaseUrl") ?? "http://localhost:8004";
        
        // Configure HTTP client
        _httpClient.Timeout = TimeSpan.FromSeconds(30);
    }

    /// <inheritdoc />
    public async Task<MLPredictionResponse?> GetRacePredictionsAsync(string marketId)
    {
        try
        {
            _logger.LogInformation("🤖 Getting ML predictions for market {MarketId}", marketId);
            
            var response = await _httpClient.GetAsync($"{_apiBaseUrl}/predict/{marketId}");
            
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("ML API returned {StatusCode} for market {MarketId}", 
                    response.StatusCode, marketId);
                return null;
            }
            
            var jsonContent = await response.Content.ReadAsStringAsync();
            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            };
            
            var predictions = JsonSerializer.Deserialize<MLPredictionResponse>(jsonContent, options);
            
            _logger.LogInformation("✅ Retrieved {Count} predictions for market {MarketId}", 
                predictions?.Predictions?.Count ?? 0, marketId);
                
            return predictions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error getting ML predictions for market {MarketId}", marketId);
            return null;
        }
    }

    /// <inheritdoc />
    public async Task<bool> ShouldPlaceBetAsync(string marketId, long selectionId, double minConfidence = 0.6)
    {
        try
        {
            var predictions = await GetRacePredictionsAsync(marketId);
            if (predictions == null)
            {
                _logger.LogWarning("No ML predictions available for market {MarketId}", marketId);
                return false;
            }

            // Find the horse prediction
            var horsePrediction = predictions.Predictions
                .FirstOrDefault(p => p.SelectionId == selectionId.ToString());
                
            if (horsePrediction == null)
            {
                _logger.LogWarning("No prediction found for selection {SelectionId} in market {MarketId}", 
                    selectionId, marketId);
                return false;
            }

            // Apply betting rules
            var shouldBet = ShouldBetOnHorse(horsePrediction, minConfidence);
            
            _logger.LogInformation("🎯 ML Betting Decision for {HorseName}: {Decision} (Confidence: {Confidence:P1})", 
                horsePrediction.HorseName, shouldBet ? "BET" : "SKIP", horsePrediction.PlaceProbability);
                
            return shouldBet;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error determining bet decision for selection {SelectionId}", selectionId);
            return false;
        }
    }

    /// <inheritdoc />
    public async Task<List<MLBettingRecommendation>> GetBettingRecommendationsAsync(string marketId)
    {
        try
        {
            var predictions = await GetRacePredictionsAsync(marketId);
            if (predictions == null)
            {
                return new List<MLBettingRecommendation>();
            }

            return predictions.BettingRecommendations;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "❌ Error getting betting recommendations for market {MarketId}", marketId);
            return new List<MLBettingRecommendation>();
        }
    }

    /// <summary>
    /// Internal logic to determine if we should bet on a horse for PLACE betting
    /// Optimized for low-risk, high-volume place betting automation
    /// </summary>
    private bool ShouldBetOnHorse(MLHorsePrediction horse, double minConfidence)
    {
        // Rule 1: Minimum ML confidence for place finish
        if (horse.PlaceProbability < minConfidence)
        {
            _logger.LogDebug("❌ {HorseName}: Below place confidence threshold ({Confidence:P1} < {Min:P1})", 
                horse.HorseName, horse.PlaceProbability, minConfidence);
            return false;
        }

        // Rule 2: Must have live odds available
        if (horse.BettingOdds.LowestBackPrice == null || horse.BettingOdds.LowestBackPrice <= 1.01)
        {
            _logger.LogDebug("❌ {HorseName}: No valid back price available ({Odds})", 
                horse.HorseName, horse.BettingOdds.LowestBackPrice);
            return false;
        }

        // Rule 3: EMBRACE favorites and low odds for place betting
        // Heavy favorites often have 80-90% place chances - perfect for our strategy
        if (horse.MarketPosition == "FAVOURITE" && horse.PlaceProbability > 0.8)
        {
            _logger.LogDebug("✅ {HorseName}: Strong favorite with high place probability - PERFECT for place betting", 
                horse.HorseName);
        }

        // Rule 4: Accept very low odds for place betting (even 1.02-1.10 can be profitable)
        // With automation, small consistent profits add up
        if (horse.BettingOdds.LowestBackPrice < 1.20)
        {
            _logger.LogDebug("ℹ️ {HorseName}: Very low odds ({Odds}) - acceptable for place betting automation", 
                horse.HorseName, horse.BettingOdds.LowestBackPrice);
        }

        // Rule 5: Must have run recently (120-day filter applied by ML model)
        if (horse.DaysOff > 120)
        {
            _logger.LogDebug("❌ {HorseName}: Too long since last race ({Days} days)", 
                horse.HorseName, horse.DaysOff);
            return false;
        }

        // Rule 6: Minimum liquidity check (ensure we can actually place the bet)
        if (horse.BettingOdds.LowestBackSize == null || horse.BettingOdds.LowestBackSize < 10)
        {
            _logger.LogDebug("❌ {HorseName}: Insufficient liquidity ({Size})", 
                horse.HorseName, horse.BettingOdds.LowestBackSize);
            return false;
        }

        // Rule 7: Market depth check (ensure active market)
        if (string.IsNullOrEmpty(horse.BettingOdds.MarketDepth) || horse.BettingOdds.MarketDepth == "SHALLOW")
        {
            _logger.LogDebug("❌ {HorseName}: No market depth ({Depth})", 
                horse.HorseName, horse.BettingOdds.MarketDepth);
            return false;
        }

        // Rule 8: Timing check - will be implemented when we have access to race event time
        // For now, we accept all timing since we're working with stored data

        _logger.LogDebug("✅ {HorseName}: Approved for place betting (Confidence: {Confidence:P1}, Odds: {Odds})", 
            horse.HorseName, horse.PlaceProbability, horse.BettingOdds.LowestBackPrice);
        return true;
    }

}
