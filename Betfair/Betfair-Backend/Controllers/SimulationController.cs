using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Betfair.Models.Simulation;
using Betfair.Services.Simulation;
using System;
using System.Threading.Tasks;
using System.Collections.Generic;
using System.Linq;

namespace Betfair.Controllers
{
    /// <summary>
    /// Controller for managing betting simulations and tracking virtual betting performance
    /// </summary>
    [ApiController]
    [Route("api/[controller]")]
    public class SimulationController : ControllerBase
    {
        private readonly IBettingSimulationService _simulationService;
        private readonly ILogger<SimulationController> _logger;

        public SimulationController(
            IBettingSimulationService simulationService,
            ILogger<SimulationController> logger)
        {
            _simulationService = simulationService;
            _logger = logger;
        }

        /// <summary>
        /// Place a simulated bet using ML predictions
        /// </summary>
        [HttpPost("place-bet")]
        public async Task<ActionResult<PlaceSimulatedBetResponse>> PlaceSimulatedBet([FromBody] PlaceSimulatedBetRequest request)
        {
            _logger.LogInformation("🎯 Placing simulated bet for market {MarketId}, selection {SelectionId}",
                request.MarketId, request.SelectionId);

            var response = await _simulationService.PlaceSimulatedBetAsync(request);
            
            if (response.BetPlaced)
            {
                return Ok(response);
            }
            else
            {
                return BadRequest(response);
            }
        }

        /// <summary>
        /// Get all simulated bets with optional date filtering
        /// </summary>
        [HttpGet("bets")]
        public async Task<ActionResult<List<SimulatedBet>>> GetSimulatedBets(
            [FromQuery] DateTime? fromDate = null,
            [FromQuery] DateTime? toDate = null)
        {
            var bets = await _simulationService.GetSimulatedBetsAsync(fromDate, toDate);
            return Ok(bets);
        }

        /// <summary>
        /// Get pending simulated bets (races not yet run)
        /// </summary>
        [HttpGet("bets/pending")]
        public async Task<ActionResult<List<SimulatedBet>>> GetPendingBets()
        {
            var bets = await _simulationService.GetPendingBetsAsync();
            return Ok(bets);
        }

        /// <summary>
        /// Manually settle bets for a market with race results
        /// </summary>
        [HttpPost("settle-market/{marketId}")]
        public async Task<ActionResult<object>> SettleMarket(
            string marketId,
            [FromBody] Dictionary<long, int> results)
        {
            _logger.LogInformation("🏁 Manually settling market {MarketId} with {Count} results",
                marketId, results.Count);

            var settledCount = await _simulationService.SettleBetsForMarketAsync(marketId, results);
            
            return Ok(new 
            { 
                MarketId = marketId,
                SettledBets = settledCount,
                Results = results,
                Message = $"Successfully settled {settledCount} bets for market {marketId}"
            });
        }

        /// <summary>
        /// Get simulation performance summary
        /// </summary>
        [HttpGet("summary")]
        public async Task<ActionResult<SimulationSummary>> GetSimulationSummary(
            [FromQuery] DateTime? fromDate = null,
            [FromQuery] DateTime? toDate = null)
        {
            var summary = await _simulationService.GetSimulationSummaryAsync(fromDate, toDate);
            return Ok(summary);
        }

        /// <summary>
        /// Get daily profit/loss breakdown
        /// </summary>
        [HttpGet("daily-pnl")]
        public async Task<ActionResult<List<DailyPnL>>> GetDailyPnL(
            [FromQuery] DateTime? fromDate = null,
            [FromQuery] DateTime? toDate = null)
        {
            var dailyPnL = await _simulationService.GetDailyPnLAsync(fromDate, toDate);
            return Ok(dailyPnL);
        }

        /// <summary>
        /// Get performance breakdown by market position
        /// </summary>
        [HttpGet("performance-by-position")]
        public async Task<ActionResult<List<MarketPositionPerformance>>> GetPerformanceByPosition(
            [FromQuery] DateTime? fromDate = null,
            [FromQuery] DateTime? toDate = null)
        {
            var performance = await _simulationService.GetPerformanceByMarketPositionAsync(fromDate, toDate);
            return Ok(performance);
        }

        /// <summary>
        /// Check for finished races and settle bets automatically
        /// </summary>
        [HttpPost("check-and-settle")]
        public async Task<ActionResult<object>> CheckAndSettleFinishedRaces()
        {
            _logger.LogInformation("🔍 Checking for finished races to settle automatically");

            var settledCount = await _simulationService.CheckAndSettleFinishedRacesAsync();
            
            return Ok(new 
            { 
                SettledBets = settledCount,
                Message = settledCount > 0 
                    ? $"Automatically settled {settledCount} bets from finished races"
                    : "No finished races found to settle"
            });
        }

        /// <summary>
        /// Get simulation dashboard data
        /// </summary>
        [HttpGet("dashboard")]
        public async Task<ActionResult<object>> GetDashboard(
            [FromQuery] int days = 7)
        {
            var fromDate = DateTime.UtcNow.AddDays(-days);
            
            var summary = await _simulationService.GetSimulationSummaryAsync(fromDate);
            var dailyPnL = await _simulationService.GetDailyPnLAsync(fromDate);
            var positionPerformance = await _simulationService.GetPerformanceByMarketPositionAsync(fromDate);
            var pendingBets = await _simulationService.GetPendingBetsAsync();

            return Ok(new
            {
                Period = $"Last {days} days",
                Summary = summary,
                DailyPnL = dailyPnL,
                PositionPerformance = positionPerformance,
                PendingBets = pendingBets.Take(10), // Show next 10 races
                RecentBets = (await _simulationService.GetSimulatedBetsAsync(fromDate)).Take(20) // Show last 20 bets
            });
        }

        /// <summary>
        /// Simulate placing bets on the current best race recommendations
        /// </summary>
        [HttpPost("auto-bet")]
        public async Task<ActionResult<object>> AutoPlaceBets(
            [FromQuery] decimal defaultStake = 10.0m,
            [FromQuery] double minConfidence = 0.7,
            [FromQuery] int maxBets = 5)
        {
            _logger.LogInformation("🤖 Auto-placing simulated bets (max: {Max}, min confidence: {MinConf:P1})",
                maxBets, minConfidence);

            // This would integrate with your race discovery service to find current races
            // For now, return a placeholder response
            
            return Ok(new 
            { 
                Message = "Auto-betting feature requires integration with live race discovery",
                Parameters = new 
                {
                    DefaultStake = defaultStake,
                    MinConfidence = minConfidence,
                    MaxBets = maxBets
                }
            });
        }
    }
}
