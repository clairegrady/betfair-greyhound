using Betfair.Services;
using Betfair.AutomationServices;

namespace Betfair.AutomatedStartupServices;
public class BetfairBackgroundWorker : BackgroundService
{
    private readonly CompetitionProcessor _competitionProcessor;
    private readonly EventAutomationService _eventAutomationService;
    private readonly MarketProcessor _marketProcessor;
    private readonly DatabaseService _databaseService;

    public BetfairBackgroundWorker(
        CompetitionProcessor competitionProcessor,
        EventAutomationService eventAutomationService,
        MarketProcessor marketProcessor, 
        DatabaseService databaseService) 
    {
        _competitionProcessor = competitionProcessor;
        _eventAutomationService = eventAutomationService;
        _marketProcessor = marketProcessor;
        _databaseService = databaseService;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await _competitionProcessor.ProcessCompetitionsAsync();
            
            var currentNbaMarketIds = await _marketProcessor.ProcessNbaMarketCataloguesAsync("10547864");
            //Console.WriteLine($"Current NBA Market IDs: {string.Join(", ", currentNbaMarketIds)}");
            await _marketProcessor.ProcessMarketBooksAsync(currentNbaMarketIds);

            await _eventAutomationService.FetchAndStoreEventTypeAsync();

            await _eventAutomationService.FetchAndStoreListOfEventsAsync(new List<string> {"7522"});

            await _marketProcessor.FetchAndStoreMarketProfitAndLossAsync(new List<string> { "1.237631444" });

            await _databaseService.DisplayMarketBooks(currentNbaMarketIds);
            
            await Task.Delay(TimeSpan.FromSeconds(120), stoppingToken);
        }
    }
}
