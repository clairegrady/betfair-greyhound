using Betfair.AutomationServices;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Microsoft.Extensions.Hosting;

namespace Betfair.Services
{
    public class HorseRacingStartupService : BackgroundService
    {
        private readonly HorseRacingAutomationService _horseRacingAutomationService;
        private readonly OrderService _orderService;
        private readonly AccountService _accountService;
        private readonly HistoricalDataService _historicalDataService;
        private readonly EventAutomationService _eventAutomationService;

        public HorseRacingStartupService(
            HorseRacingAutomationService horseRacingAutomationService,
            OrderService orderService,
            AccountService accountService,
            HistoricalDataService historicalDataService,
            EventAutomationService eventAutomationService)
        {
            _horseRacingAutomationService = horseRacingAutomationService;
            _orderService = orderService;
            _accountService = accountService;
            _historicalDataService = historicalDataService;
            _eventAutomationService = eventAutomationService;
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
                    allMarketCatalogues.AddRange(marketCatalogues);
                }

                var marketIds = allMarketCatalogues.Select(m => m.MarketId).ToList();

                if (marketIds.Any())
                {
                    // 4. Fetch and process market books for these market IDs
                    await _horseRacingAutomationService.ProcessHorseMarketBooksAsync(marketIds);
                }

                // Wait before the next iteration
                await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken);
            }
        }
    }
}