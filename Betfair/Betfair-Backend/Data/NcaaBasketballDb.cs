using Microsoft.Data.Sqlite;
using System.Collections.Generic;
using System.Threading.Tasks;
using Betfair.Models.NcaaBasketball;

namespace Betfair.Data;

public class NcaaBasketballDb
{
    private readonly string _connectionString;
    private readonly string _ncaaConnectionString;

    public NcaaBasketballDb(string betfairConnectionString)
    {
        _connectionString = betfairConnectionString;
        // NCAA basketball database is in the predictor directory
        _ncaaConnectionString = "Data Source=/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/ncaa_basketball.db";
    }

    public async Task<List<NcaaGame>> GetTodaysGamesAsync()
    {
        var games = new List<NcaaGame>();
        var today = DateTime.Now.ToString("yyyy-MM-dd");

        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                game_id,
                game_date,
                season,
                home_team_id,
                away_team_id,
                COALESCE(home_team_name, 'Unknown') as home_team,
                COALESCE(away_team_name, 'Unknown') as away_team,
                home_score,
                away_score,
                neutral_site,
                tournament
            FROM games
            WHERE game_date = @today
            ORDER BY game_id
        ";
        command.Parameters.AddWithValue("@today", today);

        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            games.Add(new NcaaGame
            {
                GameId = reader.GetString(0),
                GameDate = reader.GetString(1),
                Season = reader.GetInt32(2),
                HomeTeamId = reader.GetInt32(3),
                AwayTeamId = reader.GetInt32(4),
                HomeTeam = reader.GetString(5),
                AwayTeam = reader.GetString(6),
                HomeScore = reader.IsDBNull(7) ? null : reader.GetInt32(7),
                AwayScore = reader.IsDBNull(8) ? null : reader.GetInt32(8),
                NeutralSite = reader.GetBoolean(9),
                Tournament = reader.IsDBNull(10) ? null : reader.GetString(10)
            });
        }

        return games;
    }

    public async Task<List<NcaaGame>> GetUpcomingGamesAsync(int days = 7)
    {
        var games = new List<NcaaGame>();
        var today = DateTime.Now.ToString("yyyy-MM-dd");
        var endDate = DateTime.Now.AddDays(days).ToString("yyyy-MM-dd");

        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                game_id,
                game_date,
                game_time,
                season,
                home_team_id,
                away_team_id,
                COALESCE(home_team_name, 'Unknown') as home_team,
                COALESCE(away_team_name, 'Unknown') as away_team,
                home_score,
                away_score,
                neutral_site,
                tournament
            FROM games
            WHERE game_date >= @today AND game_date <= @endDate
            ORDER BY game_time, game_date, game_id
        ";
        command.Parameters.AddWithValue("@today", today);
        command.Parameters.AddWithValue("@endDate", endDate);

        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            games.Add(new NcaaGame
            {
                GameId = reader.GetString(0),
                GameDate = reader.GetString(1),
                GameTime = reader.IsDBNull(2) ? null : reader.GetDateTime(2),
                Season = reader.GetInt32(3),
                HomeTeamId = reader.GetInt32(4),
                AwayTeamId = reader.GetInt32(5),
                HomeTeam = reader.GetString(6),
                AwayTeam = reader.GetString(7),
                HomeScore = reader.IsDBNull(8) ? null : reader.GetInt32(8),
                AwayScore = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                NeutralSite = reader.GetBoolean(10),
                Tournament = reader.IsDBNull(11) ? null : reader.GetString(11)
            });
        }

        return games;
    }

    public async Task<NcaaTeam?> GetTeamAsync(int teamId)
    {
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                team_id,
                team_name,
                abbreviation,
                conference
            FROM teams
            WHERE team_id = @teamId
        ";
        command.Parameters.AddWithValue("@teamId", teamId);

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new NcaaTeam
            {
                TeamId = reader.GetInt32(0),
                TeamName = reader.GetString(1),
                Abbreviation = reader.IsDBNull(2) ? null : reader.GetString(2),
                Conference = reader.IsDBNull(3) ? null : reader.GetString(3)
            };
        }

        return null;
    }

    public async Task<KenPomRating?> GetKenPomRatingAsync(int teamId, int season)
    {
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                k.team_name,
                k.season,
                k.rank,
                k.adj_em,
                k.adj_o,
                k.adj_o_rank,
                k.adj_d,
                k.adj_d_rank,
                k.adj_tempo,
                k.adj_tempo_rank,
                k.sos,
                k.sos_rank,
                k.luck,
                k.luck_rank
            FROM kenpom_ratings k
            JOIN team_name_mapping m ON k.team_name = m.kenpom_team_name
            WHERE m.our_team_id = @teamId AND k.season = @season
        ";
        command.Parameters.AddWithValue("@teamId", teamId);
        command.Parameters.AddWithValue("@season", season);

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new KenPomRating
            {
                TeamName = reader.GetString(0),
                Season = reader.GetInt32(1),
                Rank = reader.IsDBNull(2) ? null : reader.GetInt32(2),
                AdjEM = reader.IsDBNull(3) ? null : reader.GetDouble(3),
                AdjO = reader.IsDBNull(4) ? null : reader.GetDouble(4),
                AdjORank = reader.IsDBNull(5) ? null : reader.GetInt32(5),
                AdjD = reader.IsDBNull(6) ? null : reader.GetDouble(6),
                AdjDRank = reader.IsDBNull(7) ? null : reader.GetInt32(7),
                AdjTempo = reader.IsDBNull(8) ? null : reader.GetDouble(8),
                AdjTempoRank = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                SOS = reader.IsDBNull(10) ? null : reader.GetDouble(10),
                SOS_Rank = reader.IsDBNull(11) ? null : reader.GetInt32(11),
                Luck = reader.IsDBNull(12) ? null : reader.GetDouble(12),
                LuckRank = reader.IsDBNull(13) ? null : reader.GetInt32(13)
            };
        }

        return null;
    }

    public async Task<List<PaperTrade>> GetPaperTradesAsync(int limit = 50)
    {
        var trades = new List<PaperTrade>();
        var paperTradesDb = "Data Source=/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/basketball_paper_trades.db";

        await using var connection = new SqliteConnection(paperTradesDb);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                id,
                placed_at,
                game_id,
                game_date,
                home_team,
                away_team,
                bet_on,
                model_probability,
                market_probability,
                edge,
                odds_taken,
                stake,
                result,
                profit_loss,
                actual_home_score,
                actual_away_score,
                settled_at
            FROM paper_trades
            ORDER BY placed_at DESC
            LIMIT @limit
        ";
        command.Parameters.AddWithValue("@limit", limit);

        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            trades.Add(new PaperTrade
            {
                Id = reader.GetInt32(0),
                PlacedAt = reader.GetDateTime(1),
                GameId = reader.GetString(2),
                GameDate = reader.GetString(3),
                HomeTeam = reader.GetString(4),
                AwayTeam = reader.GetString(5),
                BetOn = reader.GetString(6),
                ModelProbability = reader.GetDouble(7),
                MarketProbability = reader.GetDouble(8),
                Edge = reader.GetDouble(9),
                OddsTaken = reader.GetDouble(10),
                Stake = reader.GetDouble(11),
                Result = reader.GetString(12),
                ProfitLoss = reader.IsDBNull(13) ? null : reader.GetDouble(13),
                ActualHomeScore = reader.IsDBNull(14) ? null : reader.GetInt32(14),
                ActualAwayScore = reader.IsDBNull(15) ? null : reader.GetInt32(15),
                SettledAt = reader.IsDBNull(16) ? null : reader.GetDateTime(16)
            });
        }

        return trades;
    }

    public async Task<PaperTradeStats> GetPaperTradeStatsAsync()
    {
        var paperTradesDb = "Data Source=/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/basketball_paper_trades.db";

        await using var connection = new SqliteConnection(paperTradesDb);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                COUNT(*) as total_bets,
                COUNT(CASE WHEN result = 'WON' THEN 1 END) as won,
                COUNT(CASE WHEN result = 'LOST' THEN 1 END) as lost,
                COUNT(CASE WHEN result = 'PENDING' THEN 1 END) as pending,
                SUM(stake) as total_staked,
                SUM(CASE WHEN result != 'PENDING' THEN profit_loss ELSE 0 END) as total_profit,
                AVG(stake) as avg_stake,
                AVG(odds_taken) as avg_odds,
                AVG(edge) as avg_edge
            FROM paper_trades
        ";

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            var totalBets = reader.GetInt32(0);
            var won = reader.GetInt32(1);
            var lost = reader.GetInt32(2);
            var pending = reader.GetInt32(3);
            var totalStaked = reader.IsDBNull(4) ? 0 : reader.GetDouble(4);
            var totalProfit = reader.IsDBNull(5) ? 0 : reader.GetDouble(5);
            var avgStake = reader.IsDBNull(6) ? 0 : reader.GetDouble(6);
            var avgOdds = reader.IsDBNull(7) ? 0 : reader.GetDouble(7);
            var avgEdge = reader.IsDBNull(8) ? 0 : reader.GetDouble(8);

            var settled = won + lost;
            var winRate = settled > 0 ? (double)won / settled * 100 : 0;
            var roi = totalStaked > 0 ? totalProfit / totalStaked * 100 : 0;

            return new PaperTradeStats
            {
                TotalBets = totalBets,
                Won = won,
                Lost = lost,
                Pending = pending,
                Settled = settled,
                WinRate = winRate,
                TotalStaked = totalStaked,
                TotalProfit = totalProfit,
                ROI = roi,
                AvgStake = avgStake,
                AvgOdds = avgOdds,
                AvgEdge = avgEdge * 100
            };
        }

        return new PaperTradeStats();
    }

    // Methods for background service to auto-populate games

    public async Task<NcaaGame?> GetGameByTeamsAndDateAsync(string homeTeam, string awayTeam, DateTime gameTime)
    {
        var gameDate = gameTime.ToString("yyyy-MM-dd");
        
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                g.game_id,
                g.game_date,
                g.season,
                g.home_team_id,
                g.away_team_id,
                ht.team_name as home_team,
                at.team_name as away_team,
                g.home_score,
                g.away_score,
                g.neutral_site,
                g.tournament
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE ht.team_name = @homeTeam 
            AND at.team_name = @awayTeam 
            AND g.game_date = @gameDate
            LIMIT 1
        ";
        command.Parameters.AddWithValue("@homeTeam", homeTeam);
        command.Parameters.AddWithValue("@awayTeam", awayTeam);
        command.Parameters.AddWithValue("@gameDate", gameDate);

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new NcaaGame
            {
                GameId = reader.GetString(0),
                GameDate = reader.GetString(1),
                Season = reader.GetInt32(2),
                HomeTeamId = reader.GetInt32(3),
                AwayTeamId = reader.GetInt32(4),
                HomeTeam = reader.GetString(5),
                AwayTeam = reader.GetString(6),
                HomeScore = reader.IsDBNull(7) ? null : reader.GetInt32(7),
                AwayScore = reader.IsDBNull(8) ? null : reader.GetInt32(8),
                NeutralSite = reader.GetBoolean(9),
                Tournament = reader.IsDBNull(10) ? null : reader.GetString(10)
            };
        }

        return null;
    }

    public async Task<NcaaTeam?> GetTeamByNameAsync(string teamName)
    {
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT 
                team_id,
                team_name,
                abbreviation,
                conference
            FROM teams
            WHERE team_name LIKE @teamName
            LIMIT 1
        ";
        command.Parameters.AddWithValue("@teamName", $"%{teamName}%");

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new NcaaTeam
            {
                TeamId = reader.GetInt32(0),
                TeamName = reader.GetString(1),
                Abbreviation = reader.IsDBNull(2) ? null : reader.GetString(2),
                Conference = reader.IsDBNull(3) ? null : reader.GetString(3)
            };
        }

        return null;
    }

    public async Task<int> InsertTeamAsync(string teamName)
    {
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT INTO teams (team_name)
            VALUES (@teamName);
            SELECT last_insert_rowid();
        ";
        command.Parameters.AddWithValue("@teamName", teamName);

        var result = await command.ExecuteScalarAsync();
        return Convert.ToInt32(result);
    }

    public async Task InsertUpcomingGameAsync(string gameId, int homeTeamId, int awayTeamId, DateTime gameTime, string homeTeamName, string awayTeamName)
    {
        var gameDate = gameTime.ToString("yyyy-MM-dd");
        var season = gameTime.Month >= 11 ? gameTime.Year + 1 : gameTime.Year;

        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT OR IGNORE INTO games (game_id, game_date, game_time, season, home_team_id, away_team_id, home_team_name, away_team_name, neutral_site)
            VALUES (@gameId, @gameDate, @gameTime, @season, @homeTeamId, @awayTeamId, @homeTeamName, @awayTeamName, 0)
        ";
        command.Parameters.AddWithValue("@gameId", gameId);
        command.Parameters.AddWithValue("@gameDate", gameDate);
        // CRITICAL: Format DateTime as ISO8601 string for SQLite
        command.Parameters.AddWithValue("@gameTime", gameTime.ToString("yyyy-MM-dd HH:mm:ss"));
        command.Parameters.AddWithValue("@season", season);
        command.Parameters.AddWithValue("@homeTeamId", homeTeamId);
        command.Parameters.AddWithValue("@awayTeamId", awayTeamId);
        command.Parameters.AddWithValue("@homeTeamName", homeTeamName);
        command.Parameters.AddWithValue("@awayTeamName", awayTeamName);

        var rowsAffected = await command.ExecuteNonQueryAsync();
        Console.WriteLine($"💾 INSERT game_id: {gameId}, game_time: {gameTime.ToString("yyyy-MM-dd HH:mm:ss")}, rows: {rowsAffected}");
    }

    public async Task UpdateGameTimeAsync(string gameId, DateTime gameTime)
    {
        await using var connection = new SqliteConnection(_ncaaConnectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            UPDATE games 
            SET game_time = @gameTime 
            WHERE game_id = @gameId
        ";
        command.Parameters.AddWithValue("@gameId", gameId);
        // CRITICAL: Format DateTime as ISO8601 string for SQLite
        command.Parameters.AddWithValue("@gameTime", gameTime.ToString("yyyy-MM-dd HH:mm:ss"));

        var rowsAffected = await command.ExecuteNonQueryAsync();
        Console.WriteLine($"DB: UpdateGameTimeAsync game_id: {gameId}, game_time: {gameTime.ToString("yyyy-MM-dd HH:mm:ss")}, rows: {rowsAffected}");
    }

    public async Task InsertOddsAsync(string gameId, string bookmaker, double homeOdds, double awayOdds, DateTime timestamp)
    {
        // Retry logic for database lock errors
        int maxRetries = 5;
        int retryDelayMs = 100;
        
        for (int attempt = 0; attempt < maxRetries; attempt++)
        {
            try
            {
                // Store odds in the betfair database (not the NCAA predictor database)
                await using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();
                
                // Enable WAL mode for better concurrency
                using (var walCommand = connection.CreateCommand())
                {
                    walCommand.CommandText = "PRAGMA journal_mode=WAL;";
                    await walCommand.ExecuteNonQueryAsync();
                }

                // Set busy timeout to 30 seconds to handle concurrent writes
                using (var timeoutCommand = connection.CreateCommand())
                {
                    timeoutCommand.CommandText = "PRAGMA busy_timeout = 30000;";
                    await timeoutCommand.ExecuteNonQueryAsync();
                }

                // Create table if it doesn't exist
                var createTableCmd = connection.CreateCommand();
                createTableCmd.CommandText = @"
            CREATE TABLE IF NOT EXISTS ncaa_basketball_odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                home_odds REAL NOT NULL,
                away_odds REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        ";
                await createTableCmd.ExecuteNonQueryAsync();

                var command = connection.CreateCommand();
                command.CommandText = @"
            INSERT INTO ncaa_basketball_odds (game_id, bookmaker, home_odds, away_odds, timestamp)
            VALUES (@gameId, @bookmaker, @homeOdds, @awayOdds, @timestamp)
        ";
                command.Parameters.AddWithValue("@gameId", gameId);
                command.Parameters.AddWithValue("@bookmaker", bookmaker);
                command.Parameters.AddWithValue("@homeOdds", homeOdds);
                command.Parameters.AddWithValue("@awayOdds", awayOdds);
                command.Parameters.AddWithValue("@timestamp", timestamp.ToString("yyyy-MM-dd HH:mm:ss"));

                await command.ExecuteNonQueryAsync();
                
                // Success - break out of retry loop
                return;
            }
            catch (SqliteException ex) when (ex.SqliteErrorCode == 5 && attempt < maxRetries - 1) // SQLite BUSY
            {
                await Task.Delay(retryDelayMs);
                retryDelayMs *= 2; // Exponential backoff
            }
        }
        
        // If we get here, all retries failed
        throw new Exception($"Failed to insert odds for game {gameId} after multiple retries due to database lock");
    }

    public async Task<int> DeleteOldUpcomingGamesAsync(DateTime beforeDate)
    {
        // OPTION B: Smart cleanup - only delete obviously invalid/duplicate data
        // Keep ALL games (even without scores) for historical analysis
        // Keep ALL odds data for backtesting
        
        var dateStr = beforeDate.ToString("yyyy-MM-dd");
        
        // Only delete games that are:
        // 1. Very old (more than 7 days past)
        // 2. Have no scores
        // 3. Have no game_time (indicating they were malformed/test data)
        var veryOldDate = DateTime.Now.AddDays(-7).ToString("yyyy-MM-dd");
        
        await using var ncaaConnection = new SqliteConnection(_ncaaConnectionString);
        await ncaaConnection.OpenAsync();
        
        var deleteCmd = ncaaConnection.CreateCommand();
        deleteCmd.CommandText = @"
            DELETE FROM games 
            WHERE game_date < @veryOldDate 
            AND home_score IS NULL 
            AND away_score IS NULL
            AND game_time IS NULL
        ";
        deleteCmd.Parameters.AddWithValue("@veryOldDate", veryOldDate);
        
        var deletedCount = await deleteCmd.ExecuteNonQueryAsync();
        
        if (deletedCount > 0)
        {
            Console.WriteLine($"🗑️  Cleaned up {deletedCount} invalid game records (>7 days old, no scores, no game_time)");
        }
        
        return deletedCount;
        
        // Note: We do NOT delete odds data - it's valuable for backtesting
        // Note: We keep games without scores if they have valid game_time - need to investigate why scores aren't updating
    }

    public async Task<string?> FindBetfairMarketAsync(string homeTeam, string awayTeam)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        // Extract simple team name (first 2 words usually)
        var homeSimple = string.Join(" ", homeTeam.Split(' ').Take(2));
        var awaySimple = string.Join(" ", awayTeam.Split(' ').Take(2));

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT MarketId
            FROM MarketCatalogue
            WHERE CompetitionName LIKE 'NCAA Basketball%'
            AND (MarketName LIKE '%Moneyline%' OR MarketName LIKE '%Match Odds%')
            AND (
                (EventName LIKE '%' || @home || '%' AND EventName LIKE '%' || @away || '%')
                OR
                (EventName LIKE '%' || @homeSimple || '%' AND EventName LIKE '%' || @awaySimple || '%')
            )
            ORDER BY OpenDate DESC
            LIMIT 1
        ";
        command.Parameters.AddWithValue("@home", homeTeam);
        command.Parameters.AddWithValue("@away", awayTeam);
        command.Parameters.AddWithValue("@homeSimple", homeSimple);
        command.Parameters.AddWithValue("@awaySimple", awaySimple);

        var result = await command.ExecuteScalarAsync();
        return result?.ToString();
    }

    public async Task<object?> GetMarketBookAsync(string marketId)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT marketId, totalMatched, status, runners
            FROM MarketBook
            WHERE marketId = @marketId
            ORDER BY lastUpdateTime DESC
            LIMIT 1
        ";
        command.Parameters.AddWithValue("@marketId", marketId);

        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            var runnersJson = reader.GetString(3);
            return new
            {
                marketId = reader.GetString(0),
                totalMatched = reader.IsDBNull(1) ? (double?)null : reader.GetDouble(1),
                status = reader.GetString(2),
                runners = System.Text.Json.JsonSerializer.Deserialize<object>(runnersJson)
            };
        }

        return null;
    }
}

