using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Handlers;
using Betfair.Models.Market;
using Betfair.Services.Account;

namespace Betfair.AutomatedServices
{
    public class HorseRacingStartupService : BackgroundService
    {
        private readonly HorseRacingAutomationService _horseRacingAutomationService;
        private readonly EventAutomationService _eventAutomationService;
        private readonly EventDb2 _eventDb;
        private readonly AccountService _accountService;
        private readonly MarketAutomationService _marketAutomationService;
        private readonly ILogger<HorseRacingStartupService> _logger;

        public HorseRacingStartupService(
            HorseRacingAutomationService horseRacingAutomationService,
            EventAutomationService eventAutomationService,
            EventDb2 eventDb,
            AccountService accountService,
            MarketAutomationService marketAutomationService,
            ILogger<HorseRacingStartupService> logger)
        {
            _horseRacingAutomationService = horseRacingAutomationService;
            _eventAutomationService = eventAutomationService;
            _eventDb = eventDb;
            _accountService = accountService;
            _marketAutomationService = marketAutomationService;
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("🐎 HorseRacingStartupService started at {Time}", DateTime.Now);
            
            // Wait 10 seconds for network to be ready
            _logger.LogInformation("⏳ Waiting 10 seconds for network initialization...");
            await Task.Delay(10000, stoppingToken);

            int cycleCount = 0;

            while (!stoppingToken.IsCancellationRequested)
            {
                cycleCount++;
                _logger.LogInformation("🔄 Starting horse racing cycle #{CycleCount} at {Time}", cycleCount, DateTime.Now);

                try
                {
                    // 1. Fetch and store fresh horse racing events
                    _logger.LogDebug("📅 Fetching horse racing events...");
                    var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> { "7" });
                    
                    // Filter for Australian thoroughbred racing ONLY (exclude harness/trotters)
                    var auEventList = eventList
                        .Where(e => e.Event.CountryCode == "AU")
                        .Where(e => !e.Event.Name.Contains("(Pace)", StringComparison.OrdinalIgnoreCase))
                        .Where(e => !e.Event.Name.Contains("Pace", StringComparison.OrdinalIgnoreCase))
                        .Where(e => !e.Event.Name.Contains("Trots", StringComparison.OrdinalIgnoreCase))
                        .Where(e => !e.Event.Name.Contains("Harness", StringComparison.OrdinalIgnoreCase))
                        .ToList();
                    _logger.LogInformation("📊 Found {EventCount} AU thoroughbred racing events (excluded harness/trotters)", auEventList.Count);

                    // 2. Convert filtered events to strings for market catalogue fetching
                    var eventStrings = auEventList.Select(e => e.Event.Id).ToList();
                    _logger.LogDebug("🎯 Processing {EventIdCount} event IDs", eventStrings.Count);

                    // 3. Fetch market catalogues for each event
                    var allMarketCatalogues = new List<MarketCatalogue>();
                    foreach (var ev in eventStrings)
                    {
                        try
                        {
                            _logger.LogDebug("📋 Processing market catalogues for event {EventId}", ev);
                            var marketCatalogues = await _horseRacingAutomationService.GetAndProcessHorseRacingMarketCataloguesAsync(ev);
                            
                            // Filter out harness/pacing/trots markets
                            marketCatalogues = marketCatalogues
                                .Where(mc => !mc.MarketName.Contains("Pace", StringComparison.OrdinalIgnoreCase))
                                .Where(mc => !mc.MarketName.Contains("Harness", StringComparison.OrdinalIgnoreCase))
                                .Where(mc => !mc.MarketName.Contains("Trot", StringComparison.OrdinalIgnoreCase))
                                .ToList();
                            
                            _logger.LogDebug("📈 Retrieved {MarketCount} thoroughbred market catalogues for event {EventId} (filtered harness/pace)", marketCatalogues.Count, ev);

                            // Insert market catalogues for this event
                            foreach (var marketCatalogue in marketCatalogues)
                            {
                                var eventName = marketCatalogue.Event?.Name ?? "Unknown";
                                try
                                {
                                    await _eventDb.InsertEventMarketsAsync(ev, eventName, new List<MarketCatalogue> { marketCatalogue });
                                }
                                catch (Exception dbEx)
                                {
                                    _logger.LogError(dbEx, "❌ Database error inserting market catalogue for event {EventId}, market {MarketId}", ev, marketCatalogue.MarketId);
                                    // Continue with other markets rather than failing completely
                                }
                            }

                            try
                            {
                                await _eventDb.UpdateEventListWithMarketIdsAsync();
                            }
                            catch (Exception dbEx)
                            {
                                _logger.LogError(dbEx, "❌ Database error updating event list with market IDs");
                            }

                            allMarketCatalogues.AddRange(marketCatalogues);
                            
                            // Process Market Books immediately while runner lookup is populated
                            if (marketCatalogues.Any())
                            {
                                try
                                {
                                    _logger.LogDebug("🏇 Processing Market Books for event {EventId} with {MarketCount} markets", ev, marketCatalogues.Count);
                                    var eventMarketIds = marketCatalogues.Select(mc => mc.MarketId).ToList();
                                    await _horseRacingAutomationService.ProcessHorseMarketBooksAsync(eventMarketIds);
                                    _logger.LogDebug("✅ Market Books processed for event {EventId}", ev);
                                }
                                catch (Exception mbEx)
                                {
                                    _logger.LogError(mbEx, "❌ Error processing Market Books for event {EventId}", ev);
                                    // Continue with next event rather than failing completely
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "❌ Error processing market catalogues for event {EventId}", ev);
                            // Continue with next event rather than failing completely
                        }
                    }

                    var marketIds = allMarketCatalogues.Select(m => m.MarketId).ToList();
                    _logger.LogInformation("🎪 Total market IDs collected: {MarketIdCount}", marketIds.Count);

                    // Note: Horse market books are already processed per-event in the loop above (line 100)
                    // This ensures runner descriptions lookup is populated correctly for each event
                    // No need to reprocess here as it would cause missing runner names

                    if (marketIds.Any())
                    {
                        try
                        {
                            // 4. Fetch and process market books for odds/prices
                            _logger.LogDebug("📚 Processing market books for odds...");
                            await _marketAutomationService.ProcessMarketBooksAsync(marketIds);
                            _logger.LogDebug("✅ Market books processed successfully");
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "❌ Error processing market books");
                        }

                        // REMOVED: Duplicate horse market book processing
                        // This was causing 34% of horses to have no names because the runner lookup
                        // only contained the last event's runners at this point
                        // Horse market books are now processed per-event above (line 100)
                    }

                    try
                    {
                        _logger.LogDebug("💰 Fetching account funds...");
                        var accountFundsJson = await _accountService.GetAccountFundsAsync();
                        Console.WriteLine(accountFundsJson);
                        DisplayHandler.DisplayAccountData(accountFundsJson);
                        _logger.LogDebug("✅ Account funds retrieved successfully");
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "❌ Error fetching account funds");
                    }

                    _logger.LogInformation("✅ Horse racing cycle #{CycleCount} completed successfully at {Time}", cycleCount, DateTime.Now);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "💥 Critical error in horse racing cycle #{CycleCount}", cycleCount);
                    // Don't rethrow - let the service continue with the next cycle
                }

                try
                {
                    _logger.LogDebug("⏱️ Waiting 30 seconds before next cycle...");
                    await Task.Delay(TimeSpan.FromSeconds(120), stoppingToken);
                }
                catch (OperationCanceledException)
                {
                    _logger.LogInformation("🛑 HorseRacingStartupService cancellation requested");
                    break;
                }
            }

            _logger.LogInformation("🏁 HorseRacingStartupService stopped at {Time} after {CycleCount} cycles", DateTime.Now, cycleCount);
        }
    }
}