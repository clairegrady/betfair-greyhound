using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Models.Market;
using Betfair.Models.Event;

namespace Betfair.Services
{
    public class HorseRacingStartupService : BackgroundService
    {
        private readonly HorseRacingAutomationService _horseRacingAutomationService;
        private readonly EventAutomationService _eventAutomationService;
        private readonly EventDb _eventDb;

        public HorseRacingStartupService(
            HorseRacingAutomationService horseRacingAutomationService,
            EventAutomationService eventAutomationService,
            EventDb eventDb)
        {
            _horseRacingAutomationService = horseRacingAutomationService;
            _eventAutomationService = eventAutomationService;
            _eventDb = eventDb;
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

                    // Get eventName from the first MarketCatalogue's Event (if available), or fallback to "Unknown"
                    var eventName = marketCatalogues.FirstOrDefault()?.Event?.Name ?? "Unknown";

                    Console.WriteLine($"Received {marketCatalogues.Count} market catalogues for event {ev} ({eventName})");

                    await _eventDb.InsertEventMarketsAsync(ev, eventName, marketCatalogues);

                    await _eventDb.UpdateEventListWithMarketIdsAsync();

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