using Betfair.Handlers;
using Betfair.Services;
using Betfair.Services.Account;

namespace Betfair.AutomatedServices;
public class BetfairStartupServicePlaceOrder : BackgroundService
{
    private readonly CompetitionProcessor _competitionProcessor;
    private readonly MarketProcessor _marketProcessor;
    private readonly OrderService _orderService;
    private readonly AccountService _accountService;
    
    public BetfairStartupServicePlaceOrder(
        CompetitionProcessor competitionProcessor,
        MarketProcessor marketProcessor,
        OrderService orderService, 
        AccountService accountService) 
    {
        _competitionProcessor = competitionProcessor;
        _marketProcessor = marketProcessor;
        _orderService = orderService;
        _accountService = accountService;
    }
    
    public class TimeRange
    {
        public string From { get; set; }
        public string To { get; set; }
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await _competitionProcessor.ProcessCompetitionsAsync();

            var currentMarketIds = await _marketProcessor.ProcessMarketCataloguesAsync("33894244");
          
            await _marketProcessor.ProcessMarketBooksAsync(new List<string> { "1.237512511" });

            var accountFundsJson = await _accountService.GetAccountFundsAsync();
            
            DisplayHandler.DisplayAccountData(accountFundsJson); 
           
            var accountDetails = await _accountService.GetAccountDetailsAsync();
            
            try
            {
                var locale = "en_GB"; 
                var recordCount = 100;
                
                var itemDateRange = new TimeRange
                {
                    From = "2024-12-26", 
                    To = "2024-12-27"   
                };

                var includeItem = "ALL"; 
                var wallet = "UK"; 
          
                var accountStatement = await _accountService.GetAccountStatementAsync(locale, recordCount, itemDateRange, includeItem, wallet);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
            //await _databaseService.DisplayMarketBooks(currentTennisMarketIds);

            //await _orderService.PlaceOrdersAsync("1.237512511", "10109527", 1.23, 1.00, "BACK");
            
            // var instructions = new List<CancelInstruction>
            // {
            //     new CancelInstruction { betId = "372606848835" } // Provide the betId to cancel a specific bet
            // };
            // await _orderService.CancelOrderAsync("1.237598344", instructions);

            await Task.Delay(TimeSpan.FromSeconds(120), stoppingToken);
        }
    }
}
