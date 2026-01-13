using Betfair.AutomationServices;
using Betfair.Handlers;
using Betfair.Models.Data;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Betfair.Services;

namespace Betfair.AutomatedServices;
public class GreyhoundBackgroundWorker : BackgroundService
{
    private readonly GreyhoundAutomationService _greyhoundAutomationService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly IPlaceOrderService _placeOrderService;
    private readonly AccountService _accountService;
    private readonly HistoricalDataService _historicalDataService;

    public GreyhoundBackgroundWorker(
        GreyhoundAutomationService greyhoundAutomationService,
        EventAutomationService eventAutomationService,
        IPlaceOrderService placeOrderService,
        AccountService accountService,
        HistoricalDataService historicalDataService)
    {
        _greyhoundAutomationService = greyhoundAutomationService;
        _eventAutomationService = eventAutomationService;
        _placeOrderService = placeOrderService;
        _accountService = accountService;
        _historicalDataService = historicalDataService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        Console.WriteLine("GreyhoundBackgroundWorker started at {0}", DateTime.Now);
        
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Fetch Australian and New Zealand greyhound events
                var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"4339"});
                var auNzEventList = eventList.Where(e => e.Event.CountryCode == "AU" || e.Event.CountryCode == "NZ").ToList();
                
                Console.WriteLine($"Found {auNzEventList.Count} AU/NZ greyhound events (AU: {eventList.Count(e => e.Event.CountryCode == "AU")}, NZ: {eventList.Count(e => e.Event.CountryCode == "NZ")})");

                if (auNzEventList.Any())
                {
                    var eventStrings = ConvertEventListToStrings(auNzEventList);
                    var allMarketCatalogues = new List<MarketCatalogue>();

                    // Process market catalogues and books for EACH event separately (like horse racing does)
                    foreach (var ev in eventStrings)
                    {
                        try
                        {
                            Console.WriteLine($"🔍 Processing event: {ev}");
                            var marketCatalogues = await _greyhoundAutomationService.ProcessGreyhoundMarketCataloguesAsync(ev);
                            Console.WriteLine($"🔍 Got {marketCatalogues.Count} market catalogues for event {ev}");
                            
                            allMarketCatalogues.AddRange(marketCatalogues);
                            
                            // Process Market Books immediately while runner lookup is populated
                            if (marketCatalogues.Any())
                            {
                                try
                                {
                                    var eventMarketIds = marketCatalogues.Select(mc => mc.MarketId).ToList();
                                    Console.WriteLine($"🐕 Processing {eventMarketIds.Count} market books for event {ev}");
                                    await _greyhoundAutomationService.ProcessGreyhoundMarketBooksAsync(eventMarketIds);
                                    Console.WriteLine($"✅ Market Books processed for event {ev}");
                                }
                                catch (Exception mbEx)
                                {
                                    Console.WriteLine($"❌ Error processing Market Books for event {ev}: {mbEx.Message}");
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine($"❌ Error processing event {ev}: {ex.Message}");
                        }
                    }
                    
                    Console.WriteLine($"🔍 Total market catalogues collected: {allMarketCatalogues.Count}");
                }
                else
                {
                    Console.WriteLine("No AU/NZ greyhound events found");
                }

                // Wait 2 minutes before next iteration
                await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error in GreyhoundBackgroundWorker: {ex.Message}");
                await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
            }
        }
    }

    public List<string> ConvertEventListToStrings(List<EventListResult> eventList)
    {
        return eventList.Select(e => $"{e.Event.Id}").ToList();
    }
}
