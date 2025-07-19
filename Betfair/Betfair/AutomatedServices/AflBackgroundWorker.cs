using Betfair.Handlers;
using Betfair.Models.Event;
using Betfair.Services;
using Betfair.Services.Account;
using Betfair.AutomationServices;

namespace Betfair.AutomatedServices;

public class AflBackgroundWorker : BackgroundService
{
    private readonly AflService _aflService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly AccountService _accountService;

    public AflBackgroundWorker(
        AflService aflService,
        EventAutomationService eventAutomationService,
        AccountService accountService)
    {
        _aflService = aflService;
        _eventAutomationService = eventAutomationService;
        _accountService = accountService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var eventList = await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> { "6420" });
            var auEventList = eventList.Where(e => e.Event.CountryCode == "AU").ToList();
            var eventIds = ConvertEventListToStrings(auEventList);

            if (!eventIds.Any())
            {
                Console.WriteLine("No AFL events found.");
                await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
                continue;
            }

            var marketCatalogues = await _aflService.ProcessAflMarketCataloguesAsync(eventIds.First());

            var marketIds = marketCatalogues
                .Select(market => market.MarketId)
                .ToList();

            await _aflService.ProcessAflMarketBooksAsync(marketIds);

            var accountFundsJson = await _accountService.GetAccountFundsAsync();
            DisplayHandler.DisplayAccountData(accountFundsJson);

            await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken);
        }
    }

    private List<string> ConvertEventListToStrings(List<EventListResult> eventList)
    {
        return eventList.Select(e => e.Event.Id).ToList();
    }
}
