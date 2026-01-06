using System.Diagnostics;
using System.Text.Json;
using Betfair.Data;
using Betfair.Models.NcaaBasketball;

namespace Betfair.Services;

public interface INcaaBasketballService
{
    Task<GamePrediction?> GetPredictionForGameAsync(string gameId);
    Task<List<GamePrediction>> GetPredictionsForTodaysGamesAsync();
}

public class NcaaBasketballService : INcaaBasketballService
{
    private readonly NcaaBasketballDb _db;
    private readonly string _pythonPath = "/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/venv/bin/python3";
    private readonly string _predictorPath = "/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor";
    private readonly ILogger<NcaaBasketballService> _logger;

    public NcaaBasketballService(NcaaBasketballDb db, ILogger<NcaaBasketballService> logger)
    {
        _db = db;
        _logger = logger;
    }

    public async Task<GamePrediction?> GetPredictionForGameAsync(string gameId)
    {
        try
        {
            _logger.LogInformation($"Getting prediction for game {gameId}");

            // Call Python script to get prediction
            var scriptPath = Path.Combine(_predictorPath, "predict_game.py");
            
            var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = _pythonPath,
                    Arguments = $"{scriptPath} {gameId}",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = _predictorPath
                }
            };

            process.Start();
            var output = await process.StandardOutput.ReadToEndAsync();
            var error = await process.StandardError.ReadToEndAsync();
            await process.WaitForExitAsync();

            if (process.ExitCode != 0)
            {
                _logger.LogError($"Python script error: {error}");
                return null;
            }

            // Parse JSON output
            var prediction = JsonSerializer.Deserialize<GamePrediction>(output, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

            return prediction;
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting prediction for game {gameId}: {ex.Message}");
            return null;
        }
    }

    public async Task<List<GamePrediction>> GetPredictionsForTodaysGamesAsync()
    {
        var predictions = new List<GamePrediction>();

        try
        {
            // Get today's games
            var games = await _db.GetTodaysGamesAsync();
            
            _logger.LogInformation($"Getting predictions for {games.Count} games today");

            // Get prediction for each game
            foreach (var game in games)
            {
                var prediction = await GetPredictionForGameAsync(game.GameId);
                if (prediction != null)
                {
                    predictions.Add(prediction);
                }
            }

            return predictions;
        }
        catch (Exception ex)
        {
            _logger.LogError($"Error getting predictions for today's games: {ex.Message}");
            return predictions;
        }
    }

    public string DetermineConfidence(double homeWinProb, double awayWinProb)
    {
        var diff = Math.Abs(homeWinProb - awayWinProb);
        
        if (diff >= 0.30) return "high";    // 65%+ vs 35%- = clear favorite
        if (diff >= 0.15) return "medium";  // 57.5%+ vs 42.5%- = slight favorite
        return "low";                        // < 57.5% = toss-up
    }
}

