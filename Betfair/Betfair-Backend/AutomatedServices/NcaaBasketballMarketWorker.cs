using Betfair.AutomationServices;

namespace Betfair.AutomatedServices
{
    /// <summary>
    /// Background service that fetches NCAA Basketball markets from Betfair
    /// Similar to MarketBackgroundWorker but specifically for basketball
    /// </summary>
    public class NcaaBasketballMarketWorker : BackgroundService
    {
        private readonly MarketAutomationService _marketAutomationService;
        private readonly ILogger<NcaaBasketballMarketWorker> _logger;
        
        // Basketball Event Type ID on Betfair
        private const string BASKETBALL_EVENT_TYPE_ID = "7522";
        
        // NCAA Competition IDs (we may need to discover these)
        // Common ones: Men's NCAA Basketball, Women's NCAA Basketball
        private readonly List<string> _ncaaCompetitionIds = new List<string>();

        public NcaaBasketballMarketWorker(
            MarketAutomationService marketAutomationService,
            ILogger<NcaaBasketballMarketWorker> logger)
        {
            _marketAutomationService = marketAutomationService;
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("🏀 NcaaBasketballMarketWorker started at {Time}", DateTime.Now);
            Console.WriteLine("🏀 NCAA Basketball Market Worker started...");
            
            // Wait 20 seconds for network to be ready (after horse racing services)
            Console.WriteLine("⏳ Waiting 20 seconds for network initialization...");
            await Task.Delay(20000, stoppingToken);

            int cycleCount = 0;

            while (!stoppingToken.IsCancellationRequested)
            {
                cycleCount++;
                _logger.LogInformation("🏀 Starting NCAA Basketball market cycle #{CycleCount} at {Time}", cycleCount, DateTime.Now);
                Console.WriteLine($"🏀 NCAA Basketball market cycle #{cycleCount} starting");

                try
                {
                    // Fetch NCAA Basketball markets from Betfair using the basketball-specific endpoint
                    Console.WriteLine($"🏀 Fetching NCAA Basketball markets from Betfair...");
                    
                    var marketDetails = await _marketAutomationService.ProcessNcaaBasketballMarketCataloguesAsync(
                        competitionId: null,  // Fetch all NCAA competitions
                        eventId: null);       // Fetch all events

                    if (marketDetails.Any())
                    {
                        _logger.LogInformation("🏀 Found {MarketCount} NCAA Basketball markets", marketDetails.Count);
                        Console.WriteLine($"🏀 Retrieved {marketDetails.Count} NCAA Basketball market details");

                        var marketIds = marketDetails.Select(md => md.MarketId).ToList();
                        Console.WriteLine($"🏀 Market IDs: {string.Join(", ", marketIds.Take(5))}...");

                        // Fetch and process market books (odds data)
                        Console.WriteLine($"🏀 Processing {marketIds.Count} NCAA Basketball market books...");
                        await _marketAutomationService.ProcessMarketBooksAsync(marketIds);
                        
                        _logger.LogInformation("🏀 NCAA Basketball market books processing completed");
                        Console.WriteLine("🏀 NCAA Basketball market books processing completed");
                    }
                    else
                    {
                        _logger.LogInformation("🏀 No NCAA Basketball markets found");
                        Console.WriteLine("🏀 No NCAA Basketball markets found, skipping");
                    }

                    // Wait 5 minutes before next cycle
                    Console.WriteLine("⏳ Waiting 5 minutes before next NCAA Basketball market cycle...");
                    await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "❌ Error in NCAA Basketball market cycle #{CycleCount}", cycleCount);
                    Console.WriteLine($"❌ NCAA Basketball market error: {ex.Message}");
                    Console.WriteLine($"   Stack trace: {ex.StackTrace}");
                    
                    // Wait 30 seconds before retrying after an error
                    await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
                }
            }

            _logger.LogInformation("🏀 NcaaBasketballMarketWorker stopped");
            Console.WriteLine("🏀 NCAA Basketball Market Worker stopped");
        }
    }
}

