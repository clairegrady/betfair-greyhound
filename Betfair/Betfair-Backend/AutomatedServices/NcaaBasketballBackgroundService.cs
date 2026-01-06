using Betfair.Data;
using Betfair.Services;

namespace Betfair.AutomatedServices
{
    /// <summary>
    /// Background service that automatically fetches NCAA Basketball games and updates the database
    /// Runs continuously like the Horse Racing service
    /// </summary>
    public class NcaaBasketballBackgroundService : BackgroundService
    {
        private readonly ILogger<NcaaBasketballBackgroundService> _logger;
        private readonly IServiceProvider _serviceProvider;
        private readonly NcaaBasketballDb _ncaaBasketballDb;
        private const string NCAA_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/ncaa_basketball.db";

        public NcaaBasketballBackgroundService(
            ILogger<NcaaBasketballBackgroundService> logger,
            IServiceProvider serviceProvider,
            NcaaBasketballDb ncaaBasketballDb)
        {
            Console.WriteLine("🏀🏀🏀 NCAA CONSTRUCTOR CALLED 🏀🏀🏀");  // Can't miss this!
            _logger = logger;
            _serviceProvider = serviceProvider;
            _ncaaBasketballDb = ncaaBasketballDb;
            _logger.LogInformation("🏀 NcaaBasketballBackgroundService CONSTRUCTOR called");
            Console.WriteLine("🏀 Constructor completed");
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            Console.WriteLine("🏀🏀🏀 NCAA ExecuteAsync CALLED 🏀🏀🏀");
            try
            {
                _logger.LogInformation("🏀 NcaaBasketballBackgroundService started at {Time}", DateTime.Now);
                Console.WriteLine($"🏀 NCAA service starting at {DateTime.Now}");

                // Wait 10 seconds for app to fully start
                await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);

                _logger.LogInformation("🏀 Starting main NCAA Basketball loop");
                Console.WriteLine("🏀 Entering main loop");
                int cycleCount = 0;

                while (!stoppingToken.IsCancellationRequested)
                {
                    cycleCount++;
                    _logger.LogInformation("🔄 Starting NCAA Basketball cycle #{CycleCount} at {Time}", cycleCount, DateTime.Now);
                    Console.WriteLine($"🔄 NCAA cycle #{cycleCount} starting");

                    try
                    {
                        Console.WriteLine("🏀 Step 1: Creating scope...");
                        using var scope = _serviceProvider.CreateScope();
                        Console.WriteLine("🏀 Step 2: Getting OddsService...");
                        var oddsService = scope.ServiceProvider.GetRequiredService<INcaaOddsService>();
                        Console.WriteLine("🏀 Step 3: Calling GetUpcomingGamesAsync...");

                        // 1. Fetch today's and tomorrow's games from The Odds API
                        _logger.LogInformation("📅 Fetching NCAA Basketball games from The Odds API...");
                        var upcomingGames = await oddsService.GetUpcomingGamesAsync();
                        Console.WriteLine($"🏀 Step 4: Got {upcomingGames.Count} games");
                        
                        if (upcomingGames.Any())
                        {
                            Console.WriteLine($"🏀 Step 5: Processing {upcomingGames.Count} games...");
                            _logger.LogInformation("📊 Found {GameCount} upcoming NCAA Basketball games", upcomingGames.Count);

                            // 2. Store games in database
                            var gamesStored = 0;
                            foreach (var game in upcomingGames)
                            {
                                try
                                {
                                    Console.WriteLine($"🏀 Processing game: {game.AwayTeam} @ {game.HomeTeam}");
                                    // Parse team names and game details
                                    var homeTeam = game.HomeTeam;
                                    var awayTeam = game.AwayTeam;
                                    var gameTime = game.CommenceTime;

                                    Console.WriteLine($"🏀 Checking if game exists...");
                                    // Check if game already exists
                                    var existingGame = await _ncaaBasketballDb.GetGameByTeamsAndDateAsync(
                                        homeTeam, awayTeam, gameTime);

                                    if (existingGame == null)
                                    {
                                        Console.WriteLine($"🏀 New game - getting team IDs...");
                                        // Insert new game
                                        var gameId = $"{game.Id}_{gameTime:yyyyMMdd}";
                                        
                                        // Get or create team IDs
                                        var homeTeamId = await GetOrCreateTeamId(homeTeam);
                                        var awayTeamId = await GetOrCreateTeamId(awayTeam);

                                        Console.WriteLine($"🏀 Inserting game into DB...");
                                        await _ncaaBasketballDb.InsertUpcomingGameAsync(
                                            gameId,
                                            homeTeamId,
                                            awayTeamId,
                                            gameTime,
                                            homeTeam,  // Pass team name
                                            awayTeam); // Pass team name

                                        gamesStored++;
                                        Console.WriteLine($"✅ Stored NEW game #{gamesStored}");
                                        _logger.LogInformation("✅ Stored game: {AwayTeam} @ {HomeTeam} at {GameTime}", 
                                            awayTeam, homeTeam, gameTime);
                                    }
                                    else
                                    {
                                        Console.WriteLine($"🏀 Game exists - updating game_time...");
                                        // Update existing game with game_time if it's NULL
                                        await _ncaaBasketballDb.UpdateGameTimeAsync(existingGame.GameId, gameTime);
                                        gamesStored++;
                                        Console.WriteLine($"✅ Updated game #{gamesStored}");
                                    }
                                }
                            catch (Exception ex)
                            {
                                _logger.LogError(ex, "❌ Error storing game: {GameId}", game.Id);
                            }
                        }

                        _logger.LogInformation("💾 Stored {GameCount} new games in database", gamesStored);

                        // 3. Fetch and store odds for all upcoming games
                        _logger.LogInformation("💰 Fetching odds for upcoming games...");
                        var oddsStored = 0;
                        
                        foreach (var game in upcomingGames)
                        {
                            try
                            {
                                if (game.Bookmakers != null && game.Bookmakers.Any())
                                {
                                    var gameId = $"{game.Id}_{game.CommenceTime:yyyyMMdd}";
                                    
                                    foreach (var bookmaker in game.Bookmakers)
                                    {
                                        if (bookmaker.Markets != null && bookmaker.Markets.Any())
                                        {
                                            var market = bookmaker.Markets.First(); // h2h market
                                            
                                            if (market.Outcomes != null && market.Outcomes.Count >= 2)
                                            {
                                                var homeOdds = market.Outcomes.FirstOrDefault(o => o.Name == game.HomeTeam)?.Price;
                                                var awayOdds = market.Outcomes.FirstOrDefault(o => o.Name == game.AwayTeam)?.Price;

                                                if (homeOdds.HasValue && awayOdds.HasValue)
                                                {
                                                    await _ncaaBasketballDb.InsertOddsAsync(
                                                        gameId,
                                                        bookmaker.Key,
                                                        homeOdds.Value,
                                                        awayOdds.Value,
                                                        DateTime.UtcNow);

                                                    oddsStored++;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                _logger.LogError(ex, "❌ Error storing odds for game: {GameId}", game.Id);
                            }
                        }

                        _logger.LogInformation("💰 Stored {OddsCount} odds updates", oddsStored);
                    }
                    else
                    {
                        _logger.LogInformation("📊 No upcoming NCAA Basketball games found");
                    }

                    // 4. Clean up old games (games that have finished)
                    try
                    {
                        var deletedCount = await _ncaaBasketballDb.DeleteOldUpcomingGamesAsync(DateTime.UtcNow.AddDays(-1));
                        if (deletedCount > 0)
                        {
                            _logger.LogInformation("🧹 Cleaned up {DeletedCount} old games", deletedCount);
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "❌ Error cleaning up old games");
                    }

                    // Wait before next cycle
                    _logger.LogInformation("⏳ Waiting 5 minutes before next cycle...");
                    await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "❌ Error in NCAA Basketball cycle #{CycleCount}", cycleCount);
                    Console.WriteLine($"❌ NCAA cycle error: {ex.Message}");
                    
                    // Wait 30 seconds before retrying after an error
                    await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
                }
            }

            Console.WriteLine("🏀 NCAA service exiting main loop");
            _logger.LogInformation("🏀 NcaaBasketballBackgroundService stopped");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "💥 FATAL: NcaaBasketballBackgroundService crashed!");
                throw; // Re-throw to see error in startup
            }
        }

        private async Task<int> GetOrCreateTeamId(string teamName)
        {
            // Try to get existing team
            var existingTeam = await _ncaaBasketballDb.GetTeamByNameAsync(teamName);
            
            if (existingTeam != null)
            {
                return existingTeam.TeamId;
            }

            // Create new team
            var teamId = await _ncaaBasketballDb.InsertTeamAsync(teamName);
            _logger.LogInformation("🆕 Created new team: {TeamName} (ID: {TeamId})", teamName, teamId);
            
            return teamId;
        }
    }
}

