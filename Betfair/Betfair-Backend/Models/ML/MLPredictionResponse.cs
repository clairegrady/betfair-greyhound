using System.Text.Json.Serialization;

namespace Betfair.Models.ML;

/// <summary>
/// Response from the Python ML prediction API
/// </summary>
public class MLPredictionResponse
{
    [JsonPropertyName("race_info")]
    public MLRaceInfo RaceInfo { get; set; } = new();
    
    [JsonPropertyName("active_horses")]
    public int ActiveHorses { get; set; }
    
    [JsonPropertyName("predictions")]
    public List<MLHorsePrediction> Predictions { get; set; } = new();
    
    [JsonPropertyName("betting_recommendations")]
    public List<MLBettingRecommendation> BettingRecommendations { get; set; } = new();
    
    [JsonPropertyName("filtered_horses")]
    public List<string> FilteredHorses { get; set; } = new();
    
    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;
    
    [JsonPropertyName("market_summary")]
    public MLMarketSummary MarketSummary { get; set; } = new();
}

/// <summary>
/// Race information from ML API
/// </summary>
public class MLRaceInfo
{
    [JsonPropertyName("market_id")]
    public string MarketId { get; set; } = string.Empty;
    
    [JsonPropertyName("event_name")]
    public string EventName { get; set; } = string.Empty;
    
    [JsonPropertyName("market_name")]
    public string MarketName { get; set; } = string.Empty;
    
    [JsonPropertyName("total_horses")]
    public int TotalHorses { get; set; }
    
    [JsonPropertyName("event_time")]
    public string EventTime { get; set; } = string.Empty;
}

/// <summary>
/// Individual horse prediction from ML
/// </summary>
public class MLHorsePrediction
{
    [JsonPropertyName("horse_name")]
    public string HorseName { get; set; } = string.Empty;
    
    [JsonPropertyName("selection_id")]
    public string SelectionId { get; set; } = string.Empty;
    
    [JsonPropertyName("jockey")]
    public string Jockey { get; set; } = string.Empty;
    
    [JsonPropertyName("form")]
    public string Form { get; set; } = string.Empty;
    
    [JsonPropertyName("days_off")]
    public int DaysOff { get; set; }
    
    [JsonPropertyName("place_probability")]
    public double PlaceProbability { get; set; }
    
    [JsonPropertyName("place_percentage")]
    public double PlacePercentage { get; set; }
    
    [JsonPropertyName("recent_wins")]
    public int RecentWins { get; set; }
    
    [JsonPropertyName("recent_places")]
    public int RecentPlaces { get; set; }
    
    [JsonPropertyName("form_avg")]
    public double FormAverage { get; set; }
    
    [JsonPropertyName("betting_odds")]
    public MLBettingOdds BettingOdds { get; set; } = new();
    
    [JsonPropertyName("market_position")]
    public string MarketPosition { get; set; } = string.Empty;
}

/// <summary>
/// Price and size structure for betting odds
/// </summary>
public class MLPriceSize
{
    [JsonPropertyName("price")]
    public double Price { get; set; }
    
    [JsonPropertyName("size")]
    public double Size { get; set; }
}

/// <summary>
/// Betting odds information from ML API
/// </summary>
public class MLBettingOdds
{
    [JsonPropertyName("lowest_back_price")]
    public double? LowestBackPrice { get; set; }
    
    [JsonPropertyName("lowest_back_size")]
    public double? LowestBackSize { get; set; }
    
    [JsonPropertyName("highest_back_price")]
    public double? HighestBackPrice { get; set; }
    
    [JsonPropertyName("highest_back_size")]
    public double? HighestBackSize { get; set; }
    
    [JsonPropertyName("lowest_lay_price")]
    public double? LowestLayPrice { get; set; }
    
    [JsonPropertyName("lowest_lay_size")]
    public double? LowestLaySize { get; set; }
    
    [JsonPropertyName("last_price_traded")]
    public double? LastPriceTraded { get; set; }
    
    [JsonPropertyName("total_matched")]
    public double? TotalMatched { get; set; }
    
    [JsonPropertyName("all_back_prices")]
    public List<MLPriceSize> AllBackPrices { get; set; } = new();
    
    [JsonPropertyName("all_lay_prices")]
    public List<MLPriceSize> AllLayPrices { get; set; } = new();
    
    [JsonPropertyName("market_depth")]
    public string MarketDepth { get; set; } = string.Empty;
}

/// <summary>
/// Betting recommendation from ML analysis
/// </summary>
public class MLBettingRecommendation
{
    [JsonPropertyName("horse_name")]
    public string HorseName { get; set; } = string.Empty;
    
    [JsonPropertyName("selection_id")]
    public string SelectionId { get; set; } = string.Empty;
    
    [JsonPropertyName("recommendation")]
    public string Recommendation { get; set; } = string.Empty;
    
    [JsonPropertyName("confidence")]
    public double Confidence { get; set; }
    
    [JsonPropertyName("reason")]
    public string Reason { get; set; } = string.Empty;
    
    [JsonPropertyName("suggested_stake")]
    public double SuggestedStake { get; set; }
}

/// <summary>
/// Market summary statistics
/// </summary>
public class MLMarketSummary
{
    [JsonPropertyName("total_horses")]
    public int TotalHorses { get; set; }
    
    [JsonPropertyName("active_horses")]
    public int ActiveHorses { get; set; }
    
    [JsonPropertyName("filtered_horses")]
    public List<string> FilteredHorses { get; set; } = new();
    
    [JsonPropertyName("favorites_count")]
    public int FavoritesCount { get; set; }
    
    [JsonPropertyName("short_prices_count")]
    public int ShortPricesCount { get; set; }
    
    [JsonPropertyName("avg_back_price")]
    public double AverageBackPrice { get; set; }
}
