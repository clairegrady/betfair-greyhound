using System.ComponentModel.DataAnnotations;

namespace Betfair.Models.Account;

/// <summary>
/// Request model for placing ML-enhanced bets
/// </summary>
public class MLPlaceOrderRequest
{
    /// <summary>
    /// Betfair-Backend market ID
    /// </summary>
    [Required]
    public string MarketId { get; set; } = string.Empty;
    
    /// <summary>
    /// Horse selection ID
    /// </summary>
    [Required]
    public long SelectionId { get; set; }
    
    /// <summary>
    /// Bet amount in base currency
    /// </summary>
    [Required]
    [Range(0.01, 1000)]
    public decimal Stake { get; set; }
    
    /// <summary>
    /// Minimum ML confidence required (0.0 to 1.0)
    /// </summary>
    [Range(0.0, 1.0)]
    public double MinConfidence { get; set; } = 0.6;
    
    /// <summary>
    /// Maximum odds to accept
    /// </summary>
    [Range(1.01, 100)]
    public decimal? MaxOdds { get; set; }
    
    /// <summary>
    /// Force bet placement even if ML recommends against it
    /// </summary>
    public bool ForcePlace { get; set; } = false;
}

/// <summary>
/// Response model for ML-enhanced bet placement
/// </summary>
public class MLPlaceOrderResponse
{
    /// <summary>
    /// Whether the bet was placed
    /// </summary>
    public bool BetPlaced { get; set; }
    
    /// <summary>
    /// ML prediction confidence for this horse
    /// </summary>
    public double MLConfidence { get; set; }
    
    /// <summary>
    /// Reason for bet decision
    /// </summary>
    public string Reason { get; set; } = string.Empty;
    
    /// <summary>
    /// Horse name
    /// </summary>
    public string HorseName { get; set; } = string.Empty;
    
    /// <summary>
    /// Market position (FAVOURITE, SHORT_PRICE, etc.)
    /// </summary>
    public string MarketPosition { get; set; } = string.Empty;
    
    /// <summary>
    /// Actual betting odds used
    /// </summary>
    public decimal? OddsUsed { get; set; }
    
    /// <summary>
    /// Betfair-Backend order result (if bet was placed)
    /// </summary>
    public object? BetfairResult { get; set; }
    
    /// <summary>
    /// Timestamp of decision
    /// </summary>
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
}
