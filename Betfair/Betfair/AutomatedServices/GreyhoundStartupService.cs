using Betfair.AutomationServices;
using Betfair.Handlers;
using Betfair.Models.Data;
using Betfair.Models.Event;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;

namespace Betfair.AutomatedServices;

public class GreyhoundStartupService : BackgroundService
{
    private readonly GreyhoundAutomationService _greyhoundAutomationService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly OrderService _orderService;
    private readonly AccountService _accountService;
    private readonly HistoricalDataService _historicalDataService;
    public GreyhoundStartupService(
        GreyhoundAutomationService greyhoundAutomationService,
        EventAutomationService eventAutomationService,
        OrderService orderService, 
        AccountService accountService, 
        HistoricalDataService historicalDataService) 
    {
        _greyhoundAutomationService = greyhoundAutomationService;
        _eventAutomationService = eventAutomationService;
        _orderService = orderService;
        _accountService = accountService;
        _historicalDataService = historicalDataService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
            var request = new HistoricalDataRequest(
                sport: "Soccer", 
                plan: "Basic Plan", 
                fromDay: 1, fromMonth: 11, fromYear: 2024,
                toDay: 1, toMonth: 12, toYear: 2024,
                marketTypes: new List<string> { "WIN", "LOSS" }, 
                countries: new List<string> { "AU" },
                fileTypes: new List<string> { "E" }
            );
        
        while (!stoppingToken.IsCancellationRequested)
        {
            //_tarBz2Extractor.ProcessFolder("/Users/clairegrady/Downloads/BASIC", "/Users/clairegrady/Desktop/Betfair");
            
            var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"4339"});
            var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();

            var eventString = ConvertEventListToStrings(auEventList);
            var marketCatalogues = await _greyhoundAutomationService.ProcessGreyhoundMarketCataloguesAsync(eventString.First());

            var marketIds = marketCatalogues
                .Select(market => market.MarketId)  
                .ToList();
            await _greyhoundAutomationService.ProcessGreyhoundMarketBooksAsync(marketIds);
            var dataPackageList = await _historicalDataService.ListDataPackagesAsync();
            var filteredCollectionOptions = await _historicalDataService.GetCollectionOptionsAsync(request.Sport, request.Plan, request.FromDay, request.FromMonth, request.FromYear, request.ToDay, request.ToMonth, request.ToYear, request.MarketTypes, request.Countries, request.FileTypes);
            
            //Console.WriteLine($"Data Package List: {dataPackageList}");
            var filteredAdvDataSizeOptions = await _historicalDataService.GetDataSizeAsync(request);
            //Console.WriteLine($"Filtered Collection Options: {filteredCollectionOptions}");

            //Console.WriteLine($"Filtered Adv Data Size Options: {filteredAdvDataSizeOptions}");
            var accountFundsJson = await _accountService.GetAccountFundsAsync();
            DisplayHandler.DisplayAccountData(accountFundsJson); 
            
            //await _databaseService.DisplayMarketBooks(currentTennisMarketIds);

            //await _orderService.PlaceOrdersAsync("1.237512511", "10109527", 1.23, 1.00, "BACK");
            
            // var instructions = new List<CancelInstruction>
            // {
            //     new CancelInstruction { betId = "372606848835" } // Provide the betId to cancel a specific bet
            // };
            // await _orderService.CancelOrderAsync("1.237598344", instructions);
            
            // Wait for 10 minutes before the next request
            await Task.Delay(TimeSpan.FromSeconds(120), stoppingToken);
        }
    }
    
    public List<string> ConvertEventListToStrings(List<EventListResult> eventList)
    {
        //return eventList.Select(e => $"{e.Event.Name} ({e.Event.Id})").ToList();
        return eventList.Select(e => $"{e.Event.Id}").ToList();
    }

}

