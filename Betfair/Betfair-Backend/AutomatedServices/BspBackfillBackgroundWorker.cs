using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;
using System.Net.Http;
using System.Text;
using Betfair.Services;
using Betfair.Services.Account;
using Betfair.Settings;

namespace Betfair.AutomatedServices
{
    /// <summary>
    /// Background worker to fetch BSP (Betfair Starting Price) for settled races
    /// Runs every 30 minutes and backfills BSP for races from the last 2 days
    /// </summary>
    public class BspBackfillBackgroundWorker : BackgroundService
    {
        private readonly ILogger<BspBackfillBackgroundWorker> _logger;
        private readonly BetfairAuthService _authService;
        private readonly HttpClient _httpClient;
        private readonly IOptions<EndpointSettings> _settings;
        private readonly string _connectionString;

        public BspBackfillBackgroundWorker(
            ILogger<BspBackfillBackgroundWorker> logger,
            BetfairAuthService authService,
            HttpClient httpClient,
            IOptions<EndpointSettings> settings,
            IConfiguration configuration)
        {
            _logger = logger;
            _authService = authService;
            _httpClient = httpClient;
            _settings = settings;
            _connectionString = configuration.GetConnectionString("DefaultDb") 
                ?? throw new InvalidOperationException("DefaultDb connection string not found");
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("🏁 BSP Backfill Background Worker started");

            // Wait 5 minutes before first run (let other services start)
            await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await BackfillBspForRecentRacesAsync();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in BSP backfill process");
                }

                // Run every 30 minutes
                await Task.Delay(TimeSpan.FromMinutes(30), stoppingToken);
            }
        }

        private async Task BackfillBspForRecentRacesAsync()
        {
            _logger.LogInformation("🔍 Starting BSP backfill for recent races...");

            // Get market IDs from last 2 days that don't have BSP yet
            var marketIds = await GetMarketIdsNeedingBspAsync();

            if (!marketIds.Any())
            {
                _logger.LogInformation("✅ No markets need BSP backfill");
                return;
            }

            _logger.LogInformation($"📊 Found {marketIds.Count} markets needing BSP");

            // Fetch BSP in batches of 40 (Betfair limit)
            const int batchSize = 40;
            var totalProcessed = 0;
            var totalBspSaved = 0;

            for (int i = 0; i < marketIds.Count; i += batchSize)
            {
                var batch = marketIds.Skip(i).Take(batchSize).ToList();
                
                try
                {
                    var bspData = await FetchBspFromBetfairAsync(batch);
                    var savedCount = await SaveBspToDatabase(bspData);
                    
                    totalProcessed += batch.Count;
                    totalBspSaved += savedCount;
                    
                    _logger.LogInformation($"✅ Batch {i / batchSize + 1}: Processed {batch.Count} markets, saved {savedCount} BSP records");
                    
                    // Small delay between batches
                    if (i + batchSize < marketIds.Count)
                    {
                        await Task.Delay(TimeSpan.FromMilliseconds(200));
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, $"Error processing BSP batch {i / batchSize + 1}");
                }
            }

            _logger.LogInformation($"🏁 BSP Backfill complete: {totalProcessed} markets processed, {totalBspSaved} BSP records saved");
        }

        private async Task<List<string>> GetMarketIdsNeedingBspAsync()
        {
            var marketIds = new List<string>();

            try
            {
                using var connection = new NpgsqlConnection(_connectionString);
                await connection.OpenAsync();

                // Get distinct market IDs from last 2 days from both horse and greyhound tables
                // Only get markets that don't already have BSP in StreamBspProjections
                var query = @"
                    SELECT DISTINCT marketid 
                    FROM (
                        SELECT DISTINCT marketid, eventname
                        FROM horsemarketbook
                        WHERE eventname ILIKE '%' || TO_CHAR(NOW() - INTERVAL '1 day', 'DD') || '%'
                           OR eventname ILIKE '%' || TO_CHAR(NOW() - INTERVAL '2 day', 'DD') || '%'
                        
                        UNION
                        
                        SELECT DISTINCT marketid, eventname
                        FROM greyhoundmarketbook
                        WHERE eventname ILIKE '%' || TO_CHAR(NOW() - INTERVAL '1 day', 'DD') || '%'
                           OR eventname ILIKE '%' || TO_CHAR(NOW() - INTERVAL '2 day', 'DD') || '%'
                    ) AS combined
                    WHERE marketid NOT IN (
                        SELECT DISTINCT marketid 
                        FROM streambspprojections
                    )
                    LIMIT 200";

                using var command = new NpgsqlCommand(query, connection);
                using var reader = await command.ExecuteReaderAsync();

                while (await reader.ReadAsync())
                {
                    marketIds.Add(reader.GetString(0));
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting market IDs needing BSP");
            }

            return marketIds;
        }

        private async Task<Dictionary<string, List<RunnerBsp>>> FetchBspFromBetfairAsync(List<string> marketIds)
        {
            var result = new Dictionary<string, List<RunnerBsp>>();

            try
            {
                var sessionToken = await _authService.GetSessionTokenAsync();

                var requestBody = new
                {
                    jsonrpc = "2.0",
                    method = "SportsAPING/v1.0/listMarketBook",
                    @params = new
                    {
                        marketIds = marketIds,
                        priceProjection = new
                        {
                            priceData = new[] { "SP_AVAILABLE", "SP_TRADED" }
                        }
                    },
                    id = 1
                };

                _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
                _httpClient.DefaultRequestHeaders.Remove("X-Application");
                _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);
                _httpClient.DefaultRequestHeaders.Add("X-Application", _authService.AppKey);

                var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
                var response = await _httpClient.PostAsync(_settings.Value.ExchangeEndpoint, content);

                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning($"Betfair API returned {response.StatusCode} for BSP fetch");
                    return result;
                }

                var jsonResponse = await response.Content.ReadAsStringAsync();
                var apiResponse = JsonSerializer.Deserialize<JsonElement>(jsonResponse);

                if (!apiResponse.TryGetProperty("result", out var resultElement))
                {
                    return result;
                }

                foreach (var market in resultElement.EnumerateArray())
                {
                    if (!market.TryGetProperty("marketId", out var marketIdElement))
                        continue;

                    var marketId = marketIdElement.GetString();
                    if (string.IsNullOrEmpty(marketId))
                        continue;

                    if (!market.TryGetProperty("runners", out var runnersElement))
                        continue;

                    var runnerBsps = new List<RunnerBsp>();

                    foreach (var runner in runnersElement.EnumerateArray())
                    {
                        if (!runner.TryGetProperty("selectionId", out var selectionIdElement))
                            continue;

                        var selectionId = selectionIdElement.GetInt64().ToString();

                        // Get BSP from sp.nearPrice, sp.farPrice, or sp.backStakeTaken/layLiabilityTaken
                        double? bsp = null;
                        double? nearPrice = null;
                        double? farPrice = null;

                        if (runner.TryGetProperty("sp", out var spElement))
                        {
                            if (spElement.TryGetProperty("nearPrice", out var nearPriceElement))
                            {
                                nearPrice = nearPriceElement.GetDouble();
                                bsp = nearPrice;
                            }

                            if (spElement.TryGetProperty("farPrice", out var farPriceElement))
                            {
                                farPrice = farPriceElement.GetDouble();
                                if (!bsp.HasValue)
                                    bsp = farPrice;
                            }
                        }

                        if (bsp.HasValue)
                        {
                            runnerBsps.Add(new RunnerBsp
                            {
                                SelectionId = selectionId,
                                NearPrice = nearPrice,
                                FarPrice = farPrice,
                                Average = bsp.Value
                            });
                        }
                    }

                    if (runnerBsps.Any())
                    {
                        result[marketId] = runnerBsps;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching BSP from Betfair API");
            }

            return result;
        }

        private async Task<int> SaveBspToDatabase(Dictionary<string, List<RunnerBsp>> bspData)
        {
            var savedCount = 0;

            try
            {
                using var connection = new NpgsqlConnection(_connectionString);
                await connection.OpenAsync();

                foreach (var (marketId, runners) in bspData)
                {
                    foreach (var runner in runners)
                    {
                        // Get runner name from existing market data
                        var runnerName = await GetRunnerNameAsync(connection, marketId, runner.SelectionId);

                        var insertQuery = @"
                            INSERT INTO streambspprojections 
                            (marketid, selectionid, runnername, nearprice, farprice, average, updatedat)
                            VALUES (@marketid, @selectionid, @runnername, @nearprice, @farprice, @average, @updatedat)
                            ON CONFLICT (marketid, selectionid) DO UPDATE SET
                                runnername = EXCLUDED.runnername,
                                nearprice = EXCLUDED.nearprice,
                                farprice = EXCLUDED.farprice,
                                average = EXCLUDED.average,
                                updatedat = EXCLUDED.updatedat";

                        using var command = new NpgsqlCommand(insertQuery, connection);
                        command.Parameters.AddWithValue("@marketid", marketId);
                        command.Parameters.AddWithValue("@selectionid", runner.SelectionId);
                        command.Parameters.AddWithValue("@runnername", (object?)runnerName ?? DBNull.Value);
                        command.Parameters.AddWithValue("@nearprice", (object?)runner.NearPrice ?? DBNull.Value);
                        command.Parameters.AddWithValue("@farprice", (object?)runner.FarPrice ?? DBNull.Value);
                        command.Parameters.AddWithValue("@average", runner.Average);
                        command.Parameters.AddWithValue("@updatedat", DateTime.UtcNow);

                        await command.ExecuteNonQueryAsync();
                        savedCount++;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error saving BSP to database");
            }

            return savedCount;
        }

        private async Task<string?> GetRunnerNameAsync(NpgsqlConnection connection, string marketId, string selectionId)
        {
            try
            {
                // Try HorseMarketBook first
                var query = @"
                    SELECT runner_name 
                    FROM horsemarketbook 
                    WHERE marketid = @marketid AND selectionid = @selectionid 
                    LIMIT 1";

                using var command = new NpgsqlCommand(query, connection);
                command.Parameters.AddWithValue("@marketid", marketId);
                command.Parameters.AddWithValue("@selectionid", selectionId);

                var result = await command.ExecuteScalarAsync();
                if (result != null && result != DBNull.Value)
                    return result.ToString();

                // Try GreyhoundMarketBook
                query = @"
                    SELECT runnername 
                    FROM greyhoundmarketbook 
                    WHERE marketid = @marketid AND selectionid = @selectionid 
                    LIMIT 1";

                using var command2 = new NpgsqlCommand(query, connection);
                command2.Parameters.AddWithValue("@marketid", marketId);
                command2.Parameters.AddWithValue("@selectionid", selectionId);

                result = await command2.ExecuteScalarAsync();
                return result?.ToString();
            }
            catch
            {
                return null;
            }
        }

        private class RunnerBsp
        {
            public string SelectionId { get; set; } = string.Empty;
            public double? NearPrice { get; set; }
            public double? FarPrice { get; set; }
            public double Average { get; set; }
        }
    }
}
