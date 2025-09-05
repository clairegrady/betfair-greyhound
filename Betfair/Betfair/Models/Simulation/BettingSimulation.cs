using System;
using System.ComponentModel.DataAnnotations;

namespace Betfair.Models.Simulation
{
    /// <summary>
    /// Represents a simulated bet for testing betting strategies
    /// </summary>
    public class SimulatedBet
    {
        [Key]
        public int Id { get; set; }
        
        /// <summary>
        /// Market ID from Betfair
        /// </summary>
        public string MarketId { get; set; }
        
        /// <summary>
        /// Selection ID (Horse ID)
        /// </summary>
        public long SelectionId { get; set; }
        
        /// <summary>
        /// Horse name
        /// </summary>
        public string HorseName { get; set; }
        
        /// <summary>
        /// Bet type (e.g., "PLACE")
        /// </summary>
        public string BetType { get; set; } = "PLACE";
        
        /// <summary>
        /// Stake amount in pounds
        /// </summary>
        public decimal Stake { get; set; }
        
        /// <summary>
        /// Odds when bet was placed
        /// </summary>
        public decimal Odds { get; set; }
        
        /// <summary>
        /// ML confidence when bet was placed
        /// </summary>
        public double MLConfidence { get; set; }
        
        /// <summary>
        /// Market position (FAVOURITE, SHORT_PRICE, etc.)
        /// </summary>
        public string MarketPosition { get; set; }
        
        /// <summary>
        /// When the bet was placed
        /// </summary>
        public DateTime PlacedAt { get; set; }
        
        /// <summary>
        /// Race event time
        /// </summary>
        public DateTime EventTime { get; set; }
        
        /// <summary>
        /// Race event name
        /// </summary>
        public string EventName { get; set; }
        
        /// <summary>
        /// Market name
        /// </summary>
        public string MarketName { get; set; }
        
        /// <summary>
        /// Days since horse's last race
        /// </summary>
        public int DaysOff { get; set; }
        
        /// <summary>
        /// Bet status
        /// </summary>
        public BetStatus Status { get; set; } = BetStatus.Pending;
        
        /// <summary>
        /// Final finishing position (1 = winner, 2 = second, etc.)
        /// </summary>
        public int? FinishingPosition { get; set; }
        
        /// <summary>
        /// Whether the bet won (for place bets: finished 1st, 2nd, or 3rd)
        /// </summary>
        public bool? IsWinner { get; set; }
        
        /// <summary>
        /// Profit/Loss amount (negative = loss, positive = profit)
        /// </summary>
        public decimal? ProfitLoss { get; set; }
        
        /// <summary>
        /// When the bet was settled
        /// </summary>
        public DateTime? SettledAt { get; set; }
        
        /// <summary>
        /// Minutes before race start when bet was placed
        /// </summary>
        public double MinutesBeforeStart { get; set; }
        
        /// <summary>
        /// Whether timing was optimal for this bet
        /// </summary>
        public bool OptimalTiming { get; set; }
        
        /// <summary>
        /// Timing description (e.g., "30 minutes until start")
        /// </summary>
        public string TimingDescription { get; set; }
        
        /// <summary>
        /// Additional notes about the bet
        /// </summary>
        public string Notes { get; set; }
        
        /// <summary>
        /// Calculate potential winnings
        /// </summary>
        public decimal PotentialWinnings => Stake * Odds;
        
        /// <summary>
        /// Calculate potential profit
        /// </summary>
        public decimal PotentialProfit => PotentialWinnings - Stake;
    }
    
    public enum BetStatus
    {
        Pending,     // Bet placed, race not yet run
        Won,         // Bet won
        Lost,        // Bet lost
        Voided,      // Bet cancelled/voided
        Settled      // Result determined
    }
    
    /// <summary>
    /// Summary statistics for a simulation period
    /// </summary>
    public class SimulationSummary
    {
        public DateTime FromDate { get; set; }
        public DateTime ToDate { get; set; }
        public int TotalBets { get; set; }
        public int WinningBets { get; set; }
        public int LosingBets { get; set; }
        public int PendingBets { get; set; }
        public decimal TotalStaked { get; set; }
        public decimal TotalReturns { get; set; }
        public decimal TotalProfit { get; set; }
        public double WinRate { get; set; }
        public double ROI { get; set; }
        public decimal AverageStake { get; set; }
        public decimal AverageOdds { get; set; }
        public double AverageMLConfidence { get; set; }
        public decimal LargestWin { get; set; }
        public decimal LargestLoss { get; set; }
        public int ConsecutiveWins { get; set; }
        public int ConsecutiveLosses { get; set; }
        public string MostProfitableMarketPosition { get; set; }
        public double AverageMinutesBeforeStart { get; set; }
        public int OptimalTimingBets { get; set; }
        public double OptimalTimingWinRate { get; set; }
    }
    
    /// <summary>
    /// Request to place a simulated bet
    /// </summary>
    public class PlaceSimulatedBetRequest
    {
        [Required]
        public string MarketId { get; set; }
        
        [Required]
        public long SelectionId { get; set; }
        
        [Required]
        [Range(0.01, 1000.0)]
        public decimal Stake { get; set; }
        
        [Range(0.0, 1.0)]
        public double MinConfidence { get; set; } = 0.6;
        
        public bool ForcePlace { get; set; } = false;
    }
    
    /// <summary>
    /// Response from placing a simulated bet
    /// </summary>
    public class PlaceSimulatedBetResponse
    {
        public bool BetPlaced { get; set; }
        public string Reason { get; set; }
        public SimulatedBet SimulatedBet { get; set; }
        public double MLConfidence { get; set; }
        public string MarketPosition { get; set; }
        public decimal PotentialProfit { get; set; }
    }
}
