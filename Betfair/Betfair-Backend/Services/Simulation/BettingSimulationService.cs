using Betfair.Data;
using Betfair.Models.Simulation;
using Betfair.Services.ML;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Betfair.Services.Simulation
{
    /// <summary>
    /// Service for managing betting simulations and tracking virtual betting performance
    /// </summary>
    public class BettingSimulationService : IBettingSimulationService
    {
        private readonly SimulationDbContext _context;
        private readonly IMLPredictionService _mlService;
        private readonly ILogger<BettingSimulationService> _logger;

        public BettingSimulationService(
            SimulationDbContext context,
            IMLPredictionService mlService,
            ILogger<BettingSimulationService> logger)
        {
            _context = context;
            _mlService = mlService;
            _logger = logger;
        }

        public async Task<PlaceSimulatedBetResponse> PlaceSimulatedBetAsync(PlaceSimulatedBetRequest request)
        {
            _logger.LogInformation("🎯 Placing simulated bet for market {MarketId}, selection {SelectionId}, stake £{Stake}",
                request.MarketId, request.SelectionId, request.Stake);

            try
            {
                // Get ML predictions for the race
                var predictions = await _mlService.GetRacePredictionsAsync(request.MarketId);
                if (predictions == null || !predictions.Predictions.Any())
                {
                    return new PlaceSimulatedBetResponse
                    {
                        BetPlaced = false,
                        Reason = "No ML predictions available for this market"
                    };
                }

                // Find the specific horse
                var horsePrediction = predictions.Predictions.FirstOrDefault(p => p.SelectionId == request.SelectionId.ToString());
                if (horsePrediction == null)
                {
                    return new PlaceSimulatedBetResponse
                    {
                        BetPlaced = false,
                        Reason = $"Horse with selection ID {request.SelectionId} not found in predictions"
                    };
                }

                // Check if we should place the bet (unless forced)
                if (!request.ForcePlace)
                {
                    var shouldBet = await _mlService.ShouldPlaceBetAsync(request.MarketId, request.SelectionId, request.MinConfidence);
                    if (!shouldBet)
                    {
                        return new PlaceSimulatedBetResponse
                        {
                            BetPlaced = false,
                            Reason = $"ML strategy recommends against betting on {horsePrediction.HorseName}",
                            MLConfidence = horsePrediction.PlaceProbability,
                            MarketPosition = horsePrediction.MarketPosition
                        };
                    }
                }

                // Create the simulated bet
                var simulatedBet = new SimulatedBet
                {
                    MarketId = request.MarketId,
                    SelectionId = request.SelectionId,
                    HorseName = horsePrediction.HorseName,
                    BetType = "PLACE",
                    Stake = request.Stake,
                    Odds = (decimal)(horsePrediction.BettingOdds.LowestBackPrice ?? 0),
                    MLConfidence = horsePrediction.PlaceProbability,
                    MarketPosition = horsePrediction.MarketPosition,
                    PlacedAt = DateTime.UtcNow,
                    EventTime = DateTime.TryParse(predictions.RaceInfo.EventTime, out var eventTime) ? eventTime : DateTime.UtcNow.AddHours(1),
                    EventName = predictions.RaceInfo.EventName,
                    MarketName = predictions.RaceInfo.MarketName,
                    DaysOff = horsePrediction.DaysOff,
                    Status = BetStatus.Pending,
                    Notes = $"Simulated bet placed with {horsePrediction.PlaceProbability:P1} ML confidence"
                };

                // Save to database
                _context.SimulatedBets.Add(simulatedBet);
                await _context.SaveChangesAsync();

                _logger.LogInformation("✅ Simulated bet placed: {HorseName} at {Odds} for £{Stake} (Confidence: {Confidence:P1})",
                    simulatedBet.HorseName, simulatedBet.Odds, simulatedBet.Stake, simulatedBet.MLConfidence);

                return new PlaceSimulatedBetResponse
                {
                    BetPlaced = true,
                    Reason = "Simulated bet placed successfully",
                    SimulatedBet = simulatedBet,
                    MLConfidence = simulatedBet.MLConfidence,
                    MarketPosition = simulatedBet.MarketPosition,
                    PotentialProfit = simulatedBet.PotentialProfit
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "❌ Error placing simulated bet for market {MarketId}", request.MarketId);
                return new PlaceSimulatedBetResponse
                {
                    BetPlaced = false,
                    Reason = $"Error placing simulated bet: {ex.Message}"
                };
            }
        }

        public async Task<List<SimulatedBet>> GetSimulatedBetsAsync(DateTime? fromDate = null, DateTime? toDate = null)
        {
            var query = _context.SimulatedBets.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(b => b.PlacedAt >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(b => b.PlacedAt <= toDate.Value);

            return await query.OrderByDescending(b => b.PlacedAt).ToListAsync();
        }

        public async Task<List<SimulatedBet>> GetPendingBetsAsync()
        {
            return await _context.SimulatedBets
                .Where(b => b.Status == BetStatus.Pending)
                .OrderBy(b => b.EventTime)
                .ToListAsync();
        }

        public async Task<int> SettleBetsForMarketAsync(string marketId, Dictionary<long, int> results)
        {
            _logger.LogInformation("🏁 Settling bets for market {MarketId}", marketId);

            var pendingBets = await _context.SimulatedBets
                .Where(b => b.MarketId == marketId && b.Status == BetStatus.Pending)
                .ToListAsync();

            int settledCount = 0;

            foreach (var bet in pendingBets)
            {
                if (results.TryGetValue(bet.SelectionId, out int finishingPosition))
                {
                    bet.FinishingPosition = finishingPosition;
                    
                    // For place bets: win if finished 1st, 2nd, or 3rd
                    bool isWinner = bet.BetType == "PLACE" && finishingPosition <= 3;
                    bet.IsWinner = isWinner;
                    
                    if (isWinner)
                    {
                        bet.ProfitLoss = bet.PotentialProfit;
                        bet.Status = BetStatus.Won;
                        _logger.LogInformation("🏆 Bet WON: {HorseName} finished {Position} - Profit: £{Profit}",
                            bet.HorseName, finishingPosition, bet.ProfitLoss);
                    }
                    else
                    {
                        bet.ProfitLoss = -bet.Stake;
                        bet.Status = BetStatus.Lost;
                        _logger.LogInformation("❌ Bet LOST: {HorseName} finished {Position} - Loss: £{Loss}",
                            bet.HorseName, finishingPosition, bet.ProfitLoss);
                    }
                    
                    bet.SettledAt = DateTime.UtcNow;
                    settledCount++;
                }
            }

            if (settledCount > 0)
            {
                await _context.SaveChangesAsync();
                _logger.LogInformation("✅ Settled {Count} bets for market {MarketId}", settledCount, marketId);
            }

            return settledCount;
        }

        public async Task<SimulationSummary> GetSimulationSummaryAsync(DateTime? fromDate = null, DateTime? toDate = null)
        {
            var query = _context.SimulatedBets.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(b => b.PlacedAt >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(b => b.PlacedAt <= toDate.Value);

            var bets = await query.ToListAsync();
            var settledBets = bets.Where(b => b.Status != BetStatus.Pending).ToList();

            if (!bets.Any())
            {
                return new SimulationSummary
                {
                    FromDate = fromDate ?? DateTime.MinValue,
                    ToDate = toDate ?? DateTime.MaxValue
                };
            }

            var totalStaked = bets.Sum(b => b.Stake);
            var totalReturns = settledBets.Where(b => b.IsWinner == true).Sum(b => b.PotentialWinnings);
            var totalProfit = settledBets.Sum(b => b.ProfitLoss ?? 0);

            return new SimulationSummary
            {
                FromDate = fromDate ?? bets.Min(b => b.PlacedAt),
                ToDate = toDate ?? bets.Max(b => b.PlacedAt),
                TotalBets = bets.Count,
                WinningBets = settledBets.Count(b => b.IsWinner == true),
                LosingBets = settledBets.Count(b => b.IsWinner == false),
                PendingBets = bets.Count(b => b.Status == BetStatus.Pending),
                TotalStaked = totalStaked,
                TotalReturns = totalReturns,
                TotalProfit = totalProfit,
                WinRate = settledBets.Any() ? (double)settledBets.Count(b => b.IsWinner == true) / settledBets.Count : 0,
                ROI = totalStaked > 0 ? (double)(totalProfit / totalStaked) : 0,
                AverageStake = bets.Any() ? bets.Average(b => b.Stake) : 0,
                AverageOdds = bets.Any() ? bets.Average(b => b.Odds) : 0,
                AverageMLConfidence = bets.Any() ? bets.Average(b => b.MLConfidence) : 0,
                LargestWin = settledBets.Where(b => b.ProfitLoss > 0).DefaultIfEmpty().Max(b => b?.ProfitLoss ?? 0),
                LargestLoss = settledBets.Where(b => b.ProfitLoss < 0).DefaultIfEmpty().Min(b => b?.ProfitLoss ?? 0)
            };
        }

        public async Task<int> CheckAndSettleFinishedRacesAsync()
        {
            _logger.LogInformation("🔍 Checking for finished races to settle...");

            var pendingBets = await GetPendingBetsAsync();
            var finishedRaces = pendingBets
                .Where(b => b.EventTime < DateTime.UtcNow.AddMinutes(-30)) // Race finished 30+ minutes ago
                .GroupBy(b => b.MarketId)
                .ToList();

            int totalSettled = 0;

            foreach (var raceGroup in finishedRaces)
            {
                // In a real implementation, you would query the Betfair-Backend API for race results
                // For simulation, we can randomly assign results or manually input them
                _logger.LogInformation("⏰ Race {MarketId} appears to be finished, but no automatic result source configured", raceGroup.Key);
            }

            return totalSettled;
        }

        public async Task<List<DailyPnL>> GetDailyPnLAsync(DateTime? fromDate = null, DateTime? toDate = null)
        {
            var query = _context.SimulatedBets.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(b => b.PlacedAt >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(b => b.PlacedAt <= toDate.Value);

            var bets = await query.ToListAsync();

            return bets
                .GroupBy(b => b.PlacedAt.Date)
                .Select(g =>
                {
                    var dayBets = g.ToList();
                    var settledBets = dayBets.Where(b => b.Status != BetStatus.Pending).ToList();
                    var totalStaked = dayBets.Sum(b => b.Stake);
                    var totalReturns = settledBets.Where(b => b.IsWinner == true).Sum(b => b.PotentialWinnings);
                    var profitLoss = settledBets.Sum(b => b.ProfitLoss ?? 0);

                    return new DailyPnL
                    {
                        Date = g.Key,
                        TotalBets = dayBets.Count,
                        WinningBets = settledBets.Count(b => b.IsWinner == true),
                        TotalStaked = totalStaked,
                        TotalReturns = totalReturns,
                        ProfitLoss = profitLoss,
                        WinRate = settledBets.Any() ? (double)settledBets.Count(b => b.IsWinner == true) / settledBets.Count : 0,
                        ROI = totalStaked > 0 ? (double)(profitLoss / totalStaked) : 0
                    };
                })
                .OrderBy(d => d.Date)
                .ToList();
        }

        public async Task<List<MarketPositionPerformance>> GetPerformanceByMarketPositionAsync(DateTime? fromDate = null, DateTime? toDate = null)
        {
            var query = _context.SimulatedBets.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(b => b.PlacedAt >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(b => b.PlacedAt <= toDate.Value);

            var bets = await query.ToListAsync();

            return bets
                .Where(b => !string.IsNullOrEmpty(b.MarketPosition))
                .GroupBy(b => b.MarketPosition)
                .Select(g =>
                {
                    var positionBets = g.ToList();
                    var settledBets = positionBets.Where(b => b.Status != BetStatus.Pending).ToList();
                    var totalStaked = positionBets.Sum(b => b.Stake);
                    var totalReturns = settledBets.Where(b => b.IsWinner == true).Sum(b => b.PotentialWinnings);
                    var profitLoss = settledBets.Sum(b => b.ProfitLoss ?? 0);

                    return new MarketPositionPerformance
                    {
                        MarketPosition = g.Key,
                        TotalBets = positionBets.Count,
                        WinningBets = settledBets.Count(b => b.IsWinner == true),
                        TotalStaked = totalStaked,
                        TotalReturns = totalReturns,
                        ProfitLoss = profitLoss,
                        WinRate = settledBets.Any() ? (double)settledBets.Count(b => b.IsWinner == true) / settledBets.Count : 0,
                        ROI = totalStaked > 0 ? (double)(profitLoss / totalStaked) : 0,
                        AverageOdds = positionBets.Any() ? positionBets.Average(b => b.Odds) : 0,
                        AverageMLConfidence = positionBets.Any() ? positionBets.Average(b => b.MLConfidence) : 0
                    };
                })
                .OrderByDescending(p => p.ProfitLoss)
                .ToList();
        }
    }
}
