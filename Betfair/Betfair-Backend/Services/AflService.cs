using System.Text.Json;
using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Models.Runner;

namespace Betfair.Services;

public class AflService
{
    private readonly IMarketApiService _marketApiService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;

    public AflService(IMarketApiService marketApiService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb)
    {
        _marketApiService = marketApiService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
    }

    public async Task ProcessAflMarketBooksAsync(List<string> marketIds)
    {
        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);
        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson); // Fix 1: Add <ApiRunner>

        if (marketBookApiResponse?.Result?.Any() == true)
        {
            var marketBooks = marketBookApiResponse.Result
                .Where(book => book.MarketId != null)
                .Select(book => new MarketBook<ApiRunner> // Fix 2: Add <ApiRunner>
                {
                    MarketId = book.MarketId,
                    // Ensure all other properties of MarketBook<ApiRunner> are mapped here
                    IsMarketDataDelayed = book.IsMarketDataDelayed,
                    Status = book.Status,
                    BetDelay = book.BetDelay,
                    BspReconciled = book.BspReconciled,
                    Complete = book.Complete,
                    Inplay = book.Inplay,
                    NumberOfWinners = book.NumberOfWinners,
                    NumberOfRunners = book.NumberOfRunners,
                    NumberOfActiveRunners = book.NumberOfActiveRunners,
                    LastMatchTime = book.LastMatchTime,
                    TotalMatched = book.TotalMatched,
                    TotalAvailable = book.TotalAvailable,
                    CrossMatching = book.CrossMatching,
                    RunnersVoidable = book.RunnersVoidable,
                    Version = book.Version,
                    Runners = book.Runners?.Select(runner => new ApiRunner
                    {
                        SelectionId = runner.SelectionId,
                        Handicap = runner.Handicap, // Add Handicap mapping if present in ApiRunner
                        Status = runner.Status,
                        LastPriceTraded = runner.LastPriceTraded,
                        TotalMatched = runner.TotalMatched,
                        Exchange = runner.Exchange != null
                            ? new Exchange
                            {
                                AvailableToBack = runner.Exchange.AvailableToBack?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new(),
                                AvailableToLay = runner.Exchange.AvailableToLay?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new(),
                                TradedVolume = runner.Exchange.TradedVolume?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new()
                            }
                            : null,
                        Description = runner.Description // Add Description mapping if present in ApiRunner
                    }).ToList() ?? new List<ApiRunner>()
                })
                .ToList();

            if (marketBooks.Any())
            {
                // Ensure your InsertMarketBooksIntoDatabase method in MarketBookDb expects List<MarketBook<ApiRunner>>
                await _marketBookDb.InsertMarketBooksIntoDatabase(marketBooks);
            }
        }
    }

    public async Task<List<MarketDetails>> ProcessAflMarketCataloguesAsync(string eventId = null, string competitionId = null)
    {
        var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
        var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

        var filteredMarketIds = new List<MarketDetails>();

        if (marketCatalogueApiResponse?.Result != null && marketCatalogueApiResponse.Result.Any())
        {
            var marketCatalogues = marketCatalogueApiResponse.Result
                .Where(catalogue => catalogue.Event != null)
                .Select(catalogue => new MarketCatalogue
                {
                    MarketId = catalogue.MarketId,
                    MarketName = catalogue.MarketName,
                    TotalMatched = catalogue.TotalMatched,
                    EventType = catalogue.EventType != null ? new EventType { Id = catalogue.EventType.Id, Name = catalogue.EventType.Name } : null,
                    Competition = catalogue.Competition != null ? new Competition { Id = catalogue.Competition.Id, Name = catalogue.Competition.Name } : null,
                    Event = catalogue.Event != null
                        ? new Event
                        {
                            Id = catalogue.Event.Id,
                            Name = catalogue.Event.Name,
                            CountryCode = catalogue.Event.CountryCode,
                            Timezone = catalogue.Event.Timezone,
                            OpenDate = catalogue.Event.OpenDate
                        }
                        : null,
                    Runners = catalogue.Runners != null
                        ? catalogue.Runners.Select(runner => new RunnerDescription
                        {
                            SelectionId = runner.SelectionId,
                            RunnerName = runner.RunnerName,
                            Metadata = runner.Metadata // Assuming Metadata can be directly assigned, else re-instantiate
                        }).ToList()
                        : new List<RunnerDescription>(),
                })
                .ToList();

            //Console.WriteLine($"Total Market Catalogues retrieved: {marketCatalogues.Count}");
            foreach (var c in marketCatalogues)
            {
                //Console.WriteLine($"MarketId: {c.MarketId}, MarketName: {c.MarketName}, EventId: {c.Event?.Id}, EventName: {c.Event?.Name}, OpenDate: {c.Event?.OpenDate}");
            }

            var today = DateTime.Now.Date;
            filteredMarketIds = marketCatalogues
                .Where(catalogue =>
                    catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase) &&
                    catalogue.Event.OpenDate.HasValue && // Ensure OpenDate has a value before accessing .Value
                    catalogue.Event.OpenDate.Value.ToLocalTime().Date == today)
                .Select(catalogue => new MarketDetails
                {
                    MarketId = catalogue.MarketId,
                    MarketName = catalogue.MarketName
                })
                .ToList();

            if (marketCatalogues.Any())
            {
                await _listMarketCatalogueDb.InsertMarketsIntoDatabase(marketCatalogues);
            }
        }

        return filteredMarketIds;
    }
}