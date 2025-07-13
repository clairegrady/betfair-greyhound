using System.Text.Json;
using System.Text.RegularExpressions;
using Betfair.AutomationServices;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;

namespace Betfair.Services;
public class GreyhoundAutomationService
{
    private readonly IMarketService _marketService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;
    
    public GreyhoundAutomationService(IMarketService marketService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb)
    {
        _marketService = marketService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
    }
    public async Task ProcessGreyhoundMarketBooksAsync(List<string> marketIds)
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
                                AvailableToBack = runner.Exchange.AvailableToBack?.Select(p => new PriceSize
                                {
                                    Price = p.Price,
                                    Size = p.Size
                                }).ToList() ?? new List<PriceSize>(), 
                                
                                AvailableToLay = runner.Exchange.AvailableToLay?.Select(p => new PriceSize
                                {
                                    Price = p.Price,
                                    Size = p.Size
                                }).ToList() ?? new List<PriceSize>(),
                                
                                TradedVolume = runner.Exchange.TradedVolume?.Select(p => new PriceSize
                                {
                                    Price = p.Price,
                                    Size = p.Size
                                }).ToList() ?? new List<PriceSize>() 
                            }
                            : null,
                    }).ToList() ?? new List<Runner>() 
                })
                .ToList();
            
            // foreach (var book in marketBooks)
            // {
            //     foreach (var runner in book.Runners)
            //     {
            //         Console.WriteLine($"Runner {runner.SelectionId}:");
            //         Console.WriteLine($"  Available To Back: {string.Join(", ", runner.Exchange.AvailableToBack.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //         Console.WriteLine($"  Available To Lay: {string.Join(", ", runner.Exchange.AvailableToLay.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //         Console.WriteLine($"  Traded Volume: {string.Join(", ", runner.Exchange.TradedVolume.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //     }
            // }
            
            if (marketBooks.Any())
            {
                await _marketBookDb.InsertGreyhoundMarketBooksIntoDatabase(marketBooks);
            }
            else
            {
                Console.WriteLine("No market books to insert.");
            }
        }
        else
        {
            Console.WriteLine("Failed to deserialize market book or no market book data found.");
        }
    }
     public async Task<List<MarketDetails>> ProcessGreyhoundMarketCataloguesAsync(string eventId = null, string competitionId = null)
    {
        var marketCatalogueJson = await _marketService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
        var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);
    
        if (marketCatalogueApiResponse == null)
        {
            Console.WriteLine("Failed to deserialize the market catalogue JSON.");
        }
        else
        {
            Console.WriteLine($"Deserialized Market Catalogue Result Count: {marketCatalogueApiResponse.Result?.Count()}");
        }
    
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
                    EventType = catalogue.EventType != null 
                        ? new EventType
                        {
                            Id = catalogue.EventType.Id,
                            Name = catalogue.EventType.Name
                        }
                        : null,
    
                    Competition = catalogue.Competition != null 
                        ? new Competition
                        {
                            Id = catalogue.Competition.Id,
                            Name = catalogue.Competition.Name
                        }
                        : null,
    
                    Event = catalogue.Event != null 
                        ? new Event
                        {
                            Id = catalogue.Event.Id,
                            Name = catalogue.Event.Name,
                            CountryCode = catalogue.Event.CountryCode,
                            Timezone = catalogue.Event.Timezone,
                            OpenDate = catalogue.Event.OpenDate
                        }
                        : null
                })
                .Where(catalogue => catalogue.Event != null)
                .ToList();
            
            var today = DateTime.Now.Date;
            var tomorrow = today.AddDays(1);
            filteredMarketIds = marketCatalogues
                .Where(catalogue => catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase)
                                    && Regex.IsMatch(catalogue.MarketName, @"^R\d{1,2}")                                    && catalogue.Event.OpenDate.Value.ToLocalTime().Date == today)
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
            else
            {
                Console.WriteLine("No market catalogues to insert.");
            }
        }
        else
        {
            Console.WriteLine("Failed to deserialize market catalogues or no market catalogues found.");
        }
        return filteredMarketIds;
    }

}