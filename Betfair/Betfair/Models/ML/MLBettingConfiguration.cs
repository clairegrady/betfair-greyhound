namespace Betfair.Models.ML;

/// <summary>
/// Configuration for ML-based betting strategy
/// </summary>
public class MLBettingConfiguration
{
    /// <summary>
    /// Minimum ML confidence required for place bets (default 60%)
    /// </summary>
    public double MinPlaceConfidence { get; set; } = 0.6;
    
    /// <summary>
    /// Accept very low odds for high-confidence place bets (default true)
    /// </summary>
    public bool AcceptLowOdds { get; set; } = true;
    
    /// <summary>
    /// Minimum odds to accept (default 1.01 - accepts almost any odds)
    /// </summary>
    public double MinOdds { get; set; } = 1.01;
    
    /// <summary>
    /// Maximum odds to accept (default 10.0 for place betting)
    /// </summary>
    public double MaxOdds { get; set; } = 10.0;
    
    /// <summary>
    /// Favor heavy favorites for place betting (default true)
    /// </summary>
    public bool FavorFavorites { get; set; } = true;
    
    /// <summary>
    /// Minimum liquidity required in pounds (default £10)
    /// </summary>
    public double MinLiquidity { get; set; } = 10.0;
    
    /// <summary>
    /// Maximum days since last race (default 120 - filters stale horses)
    /// </summary>
    public int MaxDaysOff { get; set; } = 120;
    
    /// <summary>
    /// Default stake per bet in pounds (default £10 for low-odds place betting)
    /// </summary>
    public decimal DefaultStake { get; set; } = 10.0m;
    
    /// <summary>
    /// Enable high-volume automation mode (default true)
    /// </summary>
    public bool HighVolumeMode { get; set; } = true;
    
    /// <summary>
    /// Log level for betting decisions (Debug, Info, Warning)
    /// </summary>
    public string LogLevel { get; set; } = "Info";
    
    /// <summary>
    /// Betting timing configuration
    /// </summary>
    public BettingTimingConfiguration BettingTiming { get; set; } = new();
}

/// <summary>
/// Configuration for when to place bets relative to race start time
/// </summary>
public class BettingTimingConfiguration
{
    /// <summary>
    /// Minimum minutes before race start to place bets (default 5)
    /// </summary>
    public int MinMinutesBeforeStart { get; set; } = 5;
    
    /// <summary>
    /// Maximum minutes before race start to place bets (default 120 = 2 hours)
    /// </summary>
    public int MaxMinutesBeforeStart { get; set; } = 120;
    
    /// <summary>
    /// Preferred minutes before race start for optimal timing (default 30)
    /// </summary>
    public int PreferredMinutesBeforeStart { get; set; } = 30;
    
    /// <summary>
    /// Avoid betting once race has started (in-play) (default true)
    /// </summary>
    public bool AvoidInPlayBetting { get; set; } = true;
    
    /// <summary>
    /// Require minimum liquidity threshold based on timing (default true)
    /// </summary>
    public bool RequireMinLiquidity { get; set; } = true;
}
