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

            int cycleCount = 0;

            while (!stoppingToken.IsCancellationRequested)
            {
                cycleCount++;
                _logger.LogInformation("🔄 Starting horse racing cycle #{CycleCount} at {Time}", cycleCount, DateTime.Now);

                try
                {
                    // 1. Fetch and store fresh horse racing events
                    _logger.LogDebug("📅 Fetching horse racing events...");
                    var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> { "4339" });
                    var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();
                    _logger.LogInformation("📊 Found {EventCount} AU horse racing events", auEventList.Count);

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
                            _logger.LogDebug("📈 Retrieved {MarketCount} market catalogues for event {EventId}", marketCatalogues.Count, ev);

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
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "❌ Error processing market catalogues for event {EventId}", ev);
                            // Continue with next event rather than failing completely
                        }
                    }

                    var marketIds = allMarketCatalogues.Select(m => m.MarketId).ToList();
                    _logger.LogInformation("🎪 Total market IDs to process: {MarketIdCount}", marketIds.Count);

                    if (marketIds.Any())
                    {
                        try
                        {
                            // 4. Fetch and process market books
                            _logger.LogDebug("📚 Processing market books...");
                            await _marketAutomationService.ProcessMarketBooksAsync(marketIds);
                            _logger.LogDebug("✅ Market books processed successfully");
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "❌ Error processing market books");
                        }

                        try
                        {
                            _logger.LogDebug("🐎 Processing horse market books...");
                            await _horseRacingAutomationService.ProcessHorseMarketBooksAsync(marketIds);
                            _logger.LogDebug("✅ Horse market books processed successfully");
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "❌ Error processing horse market books");
                        }
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
                    await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
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