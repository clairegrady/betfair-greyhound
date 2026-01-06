namespace Betfair.Models.NcaaBasketball;

public class NcaaGame
{
    public string GameId { get; set; } = string.Empty;
    public string GameDate { get; set; } = string.Empty;
    public DateTime? GameTime { get; set; }  // Full datetime for game start
    public int Season { get; set; }
    public int HomeTeamId { get; set; }
    public int AwayTeamId { get; set; }
    public string HomeTeam { get; set; } = string.Empty;
    public string AwayTeam { get; set; } = string.Empty;
    public int? HomeScore { get; set; }
    public int? AwayScore { get; set; }
    public bool NeutralSite { get; set; }
    public string? Tournament { get; set; }
    
    // Computed properties for clarity
    public string Matchup => NeutralSite 
        ? $"{AwayTeam} vs {HomeTeam} (Neutral)" 
        : $"{AwayTeam} @ {HomeTeam}";
    
    public string Venue => NeutralSite ? "Neutral Court" : $"Home: {HomeTeam}";
    
    public string Result => HomeScore.HasValue && AwayScore.HasValue 
        ? $"{HomeTeam} {HomeScore} - {AwayScore} {AwayTeam}" 
        : "Not Played";
    
    public string Winner => HomeScore.HasValue && AwayScore.HasValue
        ? (HomeScore > AwayScore ? HomeTeam : AwayTeam)
        : "TBD";
    
    public string GameTimeFormatted => GameTime.HasValue 
        ? GameTime.Value.ToString("yyyy-MM-dd HH:mm") 
        : GameDate;
}

public class NcaaTeam
{
    public int TeamId { get; set; }
    public string TeamName { get; set; } = string.Empty;
    public string? Abbreviation { get; set; }
    public string? Conference { get; set; }
}

public class KenPomRating
{
    public string TeamName { get; set; } = string.Empty;
    public int Season { get; set; }
    public int? Rank { get; set; }
    public double? AdjEM { get; set; }
    public double? AdjO { get; set; }
    public int? AdjORank { get; set; }
    public double? AdjD { get; set; }
    public int? AdjDRank { get; set; }
    public double? AdjTempo { get; set; }
    public int? AdjTempoRank { get; set; }
    public double? SOS { get; set; }
    public int? SOS_Rank { get; set; }
    public double? Luck { get; set; }
    public int? LuckRank { get; set; }
}

public class GamePrediction
{
    public string GameId { get; set; } = string.Empty;
    public string HomeTeam { get; set; } = string.Empty;
    public string AwayTeam { get; set; } = string.Empty;
    public double HomeWinProbability { get; set; }
    public double AwayWinProbability { get; set; }
    public string Confidence { get; set; } = string.Empty; // "high", "medium", "low"
    public KenPomRating? HomeKenPom { get; set; }
    public KenPomRating? AwayKenPom { get; set; }
    public double? HomeEdge { get; set; }
    public double? AwayEdge { get; set; }
}

public class PaperTrade
{
    public int Id { get; set; }
    public DateTime PlacedAt { get; set; }
    public string GameId { get; set; } = string.Empty;
    public string GameDate { get; set; } = string.Empty;
    public string HomeTeam { get; set; } = string.Empty;
    public string AwayTeam { get; set; } = string.Empty;
    public string BetOn { get; set; } = string.Empty;
    public double ModelProbability { get; set; }
    public double MarketProbability { get; set; }
    public double Edge { get; set; }
    public double OddsTaken { get; set; }
    public double Stake { get; set; }
    public string Result { get; set; } = string.Empty; // "WON", "LOST", "PENDING"
    public double? ProfitLoss { get; set; }
    public int? ActualHomeScore { get; set; }
    public int? ActualAwayScore { get; set; }
    public DateTime? SettledAt { get; set; }
}

public class PaperTradeStats
{
    public int TotalBets { get; set; }
    public int Won { get; set; }
    public int Lost { get; set; }
    public int Pending { get; set; }
    public int Settled { get; set; }
    public double WinRate { get; set; }
    public double TotalStaked { get; set; }
    public double TotalProfit { get; set; }
    public double ROI { get; set; }
    public double AvgStake { get; set; }
    public double AvgOdds { get; set; }
    public double AvgEdge { get; set; }
}

