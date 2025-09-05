using Betfair.Models.ML;

namespace Betfair.Services.ML;

/// <summary>
/// Service for calling the Python ML prediction API
/// </summary>
public interface IMLPredictionService
{
    /// <summary>
    /// Get ML predictions for a specific race
    /// </summary>
    /// <param name="marketId">The Betfair market ID</param>
    /// <returns>ML prediction response with horse probabilities and betting recommendations</returns>
    Task<MLPredictionResponse?> GetRacePredictionsAsync(string marketId);
    
    /// <summary>
    /// Determine if we should place a bet based on ML analysis
    /// </summary>
    /// <param name="marketId">The Betfair market ID</param>
    /// <param name="selectionId">The horse selection ID</param>
    /// <param name="minConfidence">Minimum place probability threshold (default 60%)</param>
    /// <returns>True if bet should be placed</returns>
    Task<bool> ShouldPlaceBetAsync(string marketId, long selectionId, double minConfidence = 0.6);
    
    /// <summary>
    /// Get the best value betting opportunities from ML analysis
    /// </summary>
    /// <param name="marketId">The Betfair market ID</param>
    /// <returns>List of recommended bets</returns>
    Task<List<MLBettingRecommendation>> GetBettingRecommendationsAsync(string marketId);
}
