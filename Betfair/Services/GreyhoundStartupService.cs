using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Handlers;
using Betfair.Services.Account;

namespace Betfair.Services;

public class GreyhoundStartupService : BackgroundService
{
    private readonly GreyhoundAutomationService _greyhoundAutomationService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly OrderService _orderService;
    private readonly AccountService _accountService;
    
    public GreyhoundStartupService(
        GreyhoundAutomationService greyhoundAutomationService,
        EventAutomationService eventAutomationService,
        OrderService orderService, 
        AccountService accountService) 
    {
        _greyhoundAutomationService = greyhoundAutomationService;
        _eventAutomationService = eventAutomationService;
        _orderService = orderService;
        _accountService = accountService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"4339"});

            var marketCatalogues = await _greyhoundAutomationService.ProcessGreyhoundMarketCataloguesAsync("33895720");

            var marketIds = marketCatalogues
                .Select(market => market.MarketId)  
                .ToList();
            await _greyhoundAutomationService.ProcessGreyhoundMarketBooksAsync(marketIds);

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
}

