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
                // Fetch Australian greyhound events
                var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"4339"});
                var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();
                
                Console.WriteLine($"Found {auEventList.Count} Australian greyhound events");

                if (auEventList.Any())
                {
                    var eventStrings = ConvertEventListToStrings(auEventList);
                    var marketCatalogues = new List<MarketCatalogue>();

                    // Process market catalogues for each event
                    foreach (var ev in eventStrings)
                    {
                        try
                        {
                            Console.WriteLine($"🔍 Processing event: {ev}");
                            var result = await _greyhoundAutomationService.ProcessGreyhoundMarketCataloguesAsync(ev);
                            Console.WriteLine($"🔍 Got {result.Count} market catalogues for event {ev}");
                            marketCatalogues.AddRange(result);
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine($"❌ Error processing event {ev}: {ex.Message}");
                        }
                    }
                    
                    Console.WriteLine($"🔍 Total market catalogues collected: {marketCatalogues.Count}");

                    if (marketCatalogues.Any())
                    {
                        var marketIds = marketCatalogues
                            .Select(market => market.MarketId)
                            .ToList();

                        Console.WriteLine($"🐕 Processing {marketIds.Count} greyhound market books");
                        await _greyhoundAutomationService.ProcessGreyhoundMarketBooksAsync(marketIds);
                        Console.WriteLine($"✅ Successfully processed {marketIds.Count} greyhound markets");
                    }
                    else
                    {
                        Console.WriteLine("❌ No greyhound market catalogues found");
                    }
                }
                else
                {
                    Console.WriteLine("No Australian greyhound events found");
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
