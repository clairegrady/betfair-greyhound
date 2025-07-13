using System.Text.Json;
using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Market;

namespace Betfair.Services;

public class AflAutomationService
{
    private readonly IMarketService _marketService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;

    public AflAutomationService(IMarketService marketService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb)
    {
        _marketService = marketService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
    }

    public async Task ProcessAflMarketBooksAsync(List<string> marketIds)
    {
        var marketBookJson = await _marketService.ListMarketBookAsync(marketIds);
        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook>>(marketBookJson);

        if (marketBookApiResponse?.Result?.Any() == true)
        {
            var marketBooks = marketBookApiResponse.Result
                .Where(book => book.MarketId != null)
                .Select(book => new MarketBook
                {
                    MarketId = book.MarketId,
                    Status = book.Status,
                    BetDelay = book.BetDelay,
                    LastMatchTime = book.LastMatchTime,
                    TotalMatched = book.TotalMatched,
                    Runners = book.Runners?.Select(runner => new Runner
                    {
                        SelectionId = runner.SelectionId,
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
                    }).ToList() ?? new List<Runner>()
                })
                .ToList();

            if (marketBooks.Any())
            {
                await _marketBookDb.InsertMarketBooksIntoDatabase(marketBooks);
            }
        }
    }

    public async Task<List<MarketDetails>> ProcessAflMarketCataloguesAsync(string eventId = null, string competitionId = null)
    {
        var marketCatalogueJson = await _marketService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
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
                    EventType = catalogue.EventType,
                    Competition = catalogue.Competition,
                    Event = catalogue.Event
                })
                .ToList();

            Console.WriteLine($"Total Market Catalogues retrieved: {marketCatalogues.Count}");
            foreach (var c in marketCatalogues)
            {
                Console.WriteLine($"MarketId: {c.MarketId}, MarketName: {c.MarketName}, EventId: {c.Event?.Id}, EventName: {c.Event?.Name}, OpenDate: {c.Event?.OpenDate}");
            }
            
            var today = DateTime.Now.Date;
            filteredMarketIds = marketCatalogues
                .Where(catalogue =>
                    catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase) &&
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
