using Betfair.AutomationServices;

namespace Betfair.Services;
public class BetfairAutomationService : BackgroundService
{
    private readonly CompetitionAutomationService _competitionAutomationService;
    private readonly EventAutomationService _eventAutomationService;
    private readonly MarketAutomationService _marketAutomationService;
    private readonly DatabaseService _databaseService;

    public BetfairAutomationService(
        CompetitionAutomationService competitionAutomationService,
        EventAutomationService eventAutomationService,
        MarketAutomationService marketAutomationService, 
        DatabaseService databaseService) 
    {
        _competitionAutomationService = competitionAutomationService;
        _eventAutomationService = eventAutomationService;
        _marketAutomationService = marketAutomationService;
        _databaseService = databaseService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await _competitionAutomationService.ProcessCompetitionsAsync();
            
            var currentNbaMarketIds = await _marketAutomationService.ProcessNbaMarketCataloguesAsync("10547864");
            Console.WriteLine($"Current NBA Market IDs: {string.Join(", ", currentNbaMarketIds)}");
            await _marketAutomationService.ProcessMarketBooksAsync(currentNbaMarketIds);

            await _eventAutomationService.FetchAndStoreEventTypeAsync();

            await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"7522"});

            await _marketAutomationService.FetchAndStoreMarketProfitAndLossAsync(new List<string> { "1.237631444" });

            await _databaseService.DisplayMarketBooks(currentNbaMarketIds);
            
            await Task.Delay(TimeSpan.FromSeconds(120), stoppingToken);
        }
    }
}
