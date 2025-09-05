using Betfair.Models.Simulation;
using System.Threading.Tasks;
using System.Collections.Generic;
using System;

namespace Betfair.Services.Simulation
{
    /// <summary>
    /// Service for managing betting simulations
    /// </summary>
    public interface IBettingSimulationService
    {
        /// <summary>
        /// Place a simulated bet using ML predictions
        /// </summary>
        Task<PlaceSimulatedBetResponse> PlaceSimulatedBetAsync(PlaceSimulatedBetRequest request);
        
        /// <summary>
        /// Get all simulated bets for a date range
        /// </summary>
        Task<List<SimulatedBet>> GetSimulatedBetsAsync(DateTime? fromDate = null, DateTime? toDate = null);
        
        /// <summary>
        /// Get pending simulated bets (races not yet run)
        /// </summary>
        Task<List<SimulatedBet>> GetPendingBetsAsync();
        
        /// <summary>
        /// Update race results and settle bets for a specific market
        /// </summary>
        Task<int> SettleBetsForMarketAsync(string marketId, Dictionary<long, int> results);
        
        /// <summary>
        /// Get simulation summary statistics
        /// </summary>
        Task<SimulationSummary> GetSimulationSummaryAsync(DateTime? fromDate = null, DateTime? toDate = null);
        
        /// <summary>
        /// Check for races that have finished and attempt to settle bets
        /// </summary>
        Task<int> CheckAndSettleFinishedRacesAsync();
        
        /// <summary>
        /// Get daily P&L breakdown
        /// </summary>
        Task<List<DailyPnL>> GetDailyPnLAsync(DateTime? fromDate = null, DateTime? toDate = null);
        
        /// <summary>
        /// Get performance by market position (FAVOURITE, SHORT_PRICE, etc.)
        /// </summary>
        Task<List<MarketPositionPerformance>> GetPerformanceByMarketPositionAsync(DateTime? fromDate = null, DateTime? toDate = null);
    }
    
    /// <summary>
    /// Daily profit/loss summary
    /// </summary>
    public class DailyPnL
    {
        public DateTime Date { get; set; }
        public int TotalBets { get; set; }
        public int WinningBets { get; set; }
        public decimal TotalStaked { get; set; }
        public decimal TotalReturns { get; set; }
        public decimal ProfitLoss { get; set; }
        public double WinRate { get; set; }
        public double ROI { get; set; }
    }
    
    /// <summary>
    /// Performance breakdown by market position
    /// </summary>
    public class MarketPositionPerformance
    {
        public string MarketPosition { get; set; }
        public int TotalBets { get; set; }
        public int WinningBets { get; set; }
        public decimal TotalStaked { get; set; }
        public decimal TotalReturns { get; set; }
        public decimal ProfitLoss { get; set; }
        public double WinRate { get; set; }
        public double ROI { get; set; }
        public decimal AverageOdds { get; set; }
        public double AverageMLConfidence { get; set; }
    }
}
