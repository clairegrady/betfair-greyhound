using Betfair.AutomationServices;
using Betfair.Handlers;
using Betfair.Models.Data;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Betfair.Services.Interfaces;

namespace Betfair.Services;

public class GreyhoundStartupService : BackgroundService
{
    private readonly GreyhoundAutomationService _greyhoundAutomationService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly IPlaceOrderService _placeOrderService;
    private readonly AccountService _accountService;
    private readonly HistoricalDataService _historicalDataService;
    private readonly ILogger<GreyhoundStartupService> _logger;
    
    public GreyhoundStartupService(
        GreyhoundAutomationService greyhoundAutomationService,
        EventAutomationService eventAutomationService,
        IPlaceOrderService placeOrderService,
        AccountService accountService, 
        HistoricalDataService historicalDataService,
        ILogger<GreyhoundStartupService> logger) 
    {
        _greyhoundAutomationService = greyhoundAutomationService;
        _eventAutomationService = eventAutomationService;
        _placeOrderService = placeOrderService;
        _accountService = accountService;
        _historicalDataService = historicalDataService;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("GreyhoundStartupService started at {Time}", DateTime.Now);
        
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Fetch Australian greyhound events first
                var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"4339"});
                var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();
                
                _logger.LogInformation("Found {Count} Australian greyhound events", auEventList.Count);

                if (auEventList.Any())
                {
                    var eventStrings = ConvertEventListToStrings(auEventList);
                    var marketCatalogues = new List<MarketCatalogue>();
                    
                    // Process market catalogues for each event
                    foreach (var eventId in eventStrings)
                    {
                        var catalogues = await _greyhoundAutomationService.ProcessGreyhoundMarketCataloguesAsync(targetEventId: eventId);
                        marketCatalogues.AddRange(catalogues);
                    }
                    
                    if (marketCatalogues.Any())
                    {
                        var marketIds = marketCatalogues.Select(mc => mc.MarketId).ToList();
                        _logger.LogInformation("Found {Count} greyhound markets to process", marketIds.Count);
                        
                        // Process market books for these markets
                        await _greyhoundAutomationService.ProcessGreyhoundMarketBooksAsync(marketIds);
                        
                        _logger.LogInformation("Processed {Count} greyhound market books", marketIds.Count);
                    }
                    else
                    {
                        _logger.LogInformation("No greyhound market catalogues found");
                    }
                }
                else
                {
                    _logger.LogInformation("No Australian greyhound events found");
                }
                
                // Wait before next iteration
                await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GreyhoundStartupService");
                await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
            }
        }
    }

    public List<string> ConvertEventListToStrings(List<EventListResult> eventList)
    {
        return eventList.Select(e => $"{e.Event.Id}").ToList();
    }
}

