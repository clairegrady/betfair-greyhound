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

        public HorseRacingStartupService(
            HorseRacingAutomationService horseRacingAutomationService,
            EventAutomationService eventAutomationService,
            EventDb2 eventDb,
            AccountService accountService,
            MarketAutomationService marketAutomationService)
        {
            _horseRacingAutomationService = horseRacingAutomationService;
            _eventAutomationService = eventAutomationService;
            _eventDb = eventDb;
            _accountService = accountService;
            _marketAutomationService = marketAutomationService;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                // 1. Fetch and store fresh horse racing events (filter as needed)
                var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> { "4339" }); // horse racing eventTypeId
                var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();

                // 2. Convert filtered events to strings (event IDs) for market catalogue fetching
                var eventStrings = auEventList.Select(e => e.Event.Id).ToList();

                // 3. Fetch market catalogues for each event
                var allMarketCatalogues = new List<MarketCatalogue>();
                foreach (var ev in eventStrings)
                {
                    var marketCatalogues = await _horseRacingAutomationService.GetAndProcessHorseRacingMarketCataloguesAsync(ev);

                    // Insert all market catalogues for this event, not just the first
                    foreach (var marketCatalogue in marketCatalogues)
                    {
                        var eventName = marketCatalogue.Event?.Name ?? "Unknown";
                        await _eventDb.InsertEventMarketsAsync(ev, eventName, new List<MarketCatalogue> { marketCatalogue });
                    }

                    await _eventDb.UpdateEventListWithMarketIdsAsync();

                    allMarketCatalogues.AddRange(marketCatalogues);
                }

                var marketIds = allMarketCatalogues.Select(m => m.MarketId).ToList();

                if (marketIds.Any())
                {
                    // 4. Fetch and process market books for these market IDs
                    await _marketAutomationService.ProcessMarketBooksAsync(marketIds);
                    await _horseRacingAutomationService.ProcessHorseMarketBooksAsync(marketIds);
                }

                var accountFundsJson = await _accountService.GetAccountFundsAsync();
                Console.WriteLine("##########################################################");
                Console.WriteLine(accountFundsJson);
                DisplayHandler.DisplayAccountData(accountFundsJson);

                // Wait before the next iteration
                await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken);
            }
        }
    }
}