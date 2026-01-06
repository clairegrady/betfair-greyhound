using Microsoft.AspNetCore.Mvc;
using Betfair.Data;
using Betfair.Services;
using Betfair.Models.NcaaBasketball;
using System.Threading.Tasks;

namespace Betfair.Controllers;

[ApiController]
[Route("api/ncaa-basketball")]
public class NcaaBasketballController : ControllerBase
{
    private readonly NcaaBasketballDb _db;
    private readonly INcaaBasketballService _ncaaService;
    private readonly INcaaOddsService _oddsService;
    private readonly ILogger<NcaaBasketballController> _logger;

    public NcaaBasketballController(
        NcaaBasketballDb db, 
        INcaaBasketballService ncaaService,
        INcaaOddsService oddsService,
        ILogger<NcaaBasketballController> logger)
    {
        _db = db;
        _ncaaService = ncaaService;
        _oddsService = oddsService;
        _logger = logger;
    }

    /// <summary>
    /// Get today's NCAA basketball games
    /// </summary>
    [HttpGet("games/today")]
    public async Task<IActionResult> GetTodaysGames()
    {
        try
        {
            var games = await _db.GetTodaysGamesAsync();
            _logger.LogInformation($"Found {games.Count} games for today");
            return Ok(games);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting today's games: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get upcoming NCAA basketball games (next 7 days)
    /// </summary>
    [HttpGet("games/upcoming")]
    public async Task<IActionResult> GetUpcomingGames([FromQuery] int days = 7)
    {
        try
        {
            var games = await _db.GetUpcomingGamesAsync(days);
            _logger.LogInformation($"Found {games.Count} games in next {days} days");
            return Ok(games);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting upcoming games: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get team information
    /// </summary>
    [HttpGet("teams/{teamId}")]
    public async Task<IActionResult> GetTeam(int teamId)
    {
        try
        {
            var team = await _db.GetTeamAsync(teamId);
            if (team == null)
            {
                return NotFound(new { error = $"Team {teamId} not found" });
            }
            return Ok(team);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting team {teamId}: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get KenPom ratings for a team
    /// </summary>
    [HttpGet("kenpom/{teamId}")]
    public async Task<IActionResult> GetKenPomRating(int teamId, [FromQuery] int season = 2025)
    {
        try
        {
            var rating = await _db.GetKenPomRatingAsync(teamId, season);
            if (rating == null)
            {
                return NotFound(new { error = $"KenPom rating not found for team {teamId} in season {season}" });
            }
            return Ok(rating);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting KenPom rating for team {teamId}: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get model prediction for a specific game
    /// </summary>
    [HttpGet("predictions/{gameId}")]
    public async Task<IActionResult> GetPrediction(string gameId)
    {
        try
        {
            _logger.LogInformation($"Getting prediction for game {gameId}");
            var prediction = await _ncaaService.GetPredictionForGameAsync(gameId);
            
            if (prediction == null)
            {
                return NotFound(new { error = $"Could not generate prediction for game {gameId}" });
            }
            
            return Ok(prediction);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting prediction for game {gameId}: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get model predictions for today's games
    /// </summary>
    [HttpGet("predictions/today")]
    public async Task<IActionResult> GetTodaysPredictions()
    {
        try
        {
            _logger.LogInformation("Getting predictions for today's games");
            var predictions = await _ncaaService.GetPredictionsForTodaysGamesAsync();
            return Ok(predictions);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting today's predictions: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get paper trading history
    /// </summary>
    [HttpGet("paper-trades")]
    public async Task<IActionResult> GetPaperTrades([FromQuery] int limit = 50)
    {
        try
        {
            var trades = await _db.GetPaperTradesAsync(limit);
            return Ok(trades);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting paper trades: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get paper trading statistics
    /// </summary>
    [HttpGet("paper-trades/stats")]
    public async Task<IActionResult> GetPaperTradeStats()
    {
        try
        {
            var stats = await _db.GetPaperTradeStatsAsync();
            return Ok(stats);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting paper trade stats: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get current odds for today's games
    /// </summary>
    [HttpGet("odds/today")]
    public async Task<IActionResult> GetTodaysOdds()
    {
        try
        {
            var odds = await _oddsService.GetTodaysOddsAsync();
            return Ok(odds);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting today's odds: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get predictions with odds comparison
    /// </summary>
    [HttpGet("predictions-with-odds/today")]
    public async Task<IActionResult> GetTodaysPredictionsWithOdds()
    {
        try
        {
            _logger.LogInformation("Getting predictions with odds for today's games");
            
            var predictions = await _ncaaService.GetPredictionsForTodaysGamesAsync();
            var odds = await _oddsService.GetTodaysOddsAsync();

            var results = predictions.Select(pred =>
            {
                var oddsKey = $"{pred.AwayTeam}@{pred.HomeTeam}";
                var hasOdds = odds.ContainsKey(oddsKey);
                
                var result = new
                {
                    prediction = pred,
                    odds = hasOdds ? odds[oddsKey] : null,
                    homeEdge = hasOdds ? pred.HomeWinProbability - (1.0 / odds[oddsKey].HomeOdds) : (double?)null,
                    awayEdge = hasOdds ? pred.AwayWinProbability - (1.0 / odds[oddsKey].AwayOdds) : (double?)null
                };
                
                return result;
            }).ToList();

            return Ok(results);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting predictions with odds: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Find Betfair market ID for a game by team names
    /// </summary>
    [HttpGet("find-market")]
    public async Task<IActionResult> FindBetfairMarket([FromQuery] string homeTeam, [FromQuery] string awayTeam)
    {
        try
        {
            var marketId = await _db.FindBetfairMarketAsync(homeTeam, awayTeam);
            if (marketId == null)
            {
                return NotFound(new { error = $"No Betfair market found for {awayTeam} @ {homeTeam}" });
            }
            return Ok(new { marketId });
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error finding Betfair market: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Get market book (current odds) for an NCAA basketball market from Betfair
    /// </summary>
    [HttpGet("market-book/{marketId}")]
    public async Task<IActionResult> GetMarketBook(string marketId)
    {
        try
        {
            var marketBook = await _db.GetMarketBookAsync(marketId);
            if (marketBook == null)
            {
                return NotFound(new { error = $"Market book not found for {marketId}" });
            }
            return Ok(marketBook);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting market book: {ex.Message}");
            return StatusCode(500, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Health check endpoint
    /// </summary>
    [HttpGet("health")]
    public IActionResult HealthCheck()
    {
        return Ok(new 
        { 
            status = "healthy",
            service = "NCAA Basketball API",
            timestamp = DateTime.UtcNow
        });
    }
}

