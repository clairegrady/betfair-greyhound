using System.Text.Json;
using System.Text.RegularExpressions;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Betfair.Services;

namespace Betfair.AutomationServices;
public class GreyhoundAutomationService
{
    private readonly IMarketApiService _marketApiService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;
    private readonly EventDb2 _eventDb;
    
    // Cache for runner names (MarketId -> Dictionary of SelectionId -> RunnerName)
    private readonly Dictionary<string, Dictionary<long, string>> _runnerNamesCache = new();
    
    // Cache for market metadata (MarketId -> (Venue, EventDate))
    private readonly Dictionary<string, (string? Venue, DateTime? EventDate)> _marketMetadataCache = new();
    
    public GreyhoundAutomationService(IMarketApiService marketApiService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb, EventDb2 eventDb)
    {
        _marketApiService = marketApiService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
        _eventDb = eventDb;
    }
    public async Task ProcessGreyhoundMarketBooksAsync(List<string> marketIds)
    {
        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);
        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
        if (marketBookApiResponse?.Result?.Any() == true)
        {
            var marketBooks = marketBookApiResponse.Result
                .Where(book => book.MarketId != null)
                .Select(book => new MarketBook<ApiRunner> // You need to specify <ApiRunner> here as well
                {
                    MarketId = book.MarketId,
                    Status = book.Status,
                    BetDelay = book.BetDelay,
                    LastMatchTime = book.LastMatchTime,
                    TotalMatched = book.TotalMatched,
                    Runners = book.Runners?.Select(runner => {
                        // Try to get runner name from cache (populated by ProcessGreyhoundMarketCataloguesAsync)
                        string? runnerName = null;
                        if (_runnerNamesCache.TryGetValue(book.MarketId, out var runnerMap))
                        {
                            runnerMap.TryGetValue(runner.SelectionId, out runnerName);
                        }
                        
                        return new ApiRunner
                        {
                            SelectionId = runner.SelectionId,
                            Status = runner.Status,
                            LastPriceTraded = runner.LastPriceTraded,
                            TotalMatched = runner.TotalMatched,
                            Handicap = runner.Handicap,
                            // Add Description with RunnerName from cache
                            Description = runnerName != null 
                                ? new RunnerDescription
                                {
                                    SelectionId = runner.SelectionId,
                                    RunnerName = runnerName,
                                    Metadata = runner.Description?.Metadata
                                }
                                : runner.Description, // Fall back to original if no cache entry
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
                        };
                    }).ToList() ?? new List<ApiRunner>()
                })
                .ToList();
            
            // foreach (var book in marketBooks)
            // {
            //     foreach (var runner in book.Runners)
            //     {
            //         //Console.WriteLine($"Runner {runner.SelectionId}:");
            //         //Console.WriteLine($"  Available To Back: {string.Join(", ", runner.Exchange.AvailableToBack.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //         //Console.WriteLine($"  Available To Lay: {string.Join(", ", runner.Exchange.AvailableToLay.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //         //Console.WriteLine($"  Traded Volume: {string.Join(", ", runner.Exchange.TradedVolume.Select(x => $"Price: {x.Price}, Size: {x.Size}"))}");
            //     }
            // }
            
            if (marketBooks.Any())
            {
                Console.WriteLine($"🐕 Inserting {marketBooks.Count} greyhound market books into database...");
                await _marketBookDb.InsertGreyhoundMarketBooksIntoDatabase(marketBooks);
                Console.WriteLine($"✅ Successfully inserted {marketBooks.Count} greyhound market books");
            }
            else
            {
                Console.WriteLine("❌ No greyhound market books to insert.");
            }
        }
        else
        {
            //Console.WriteLine("Failed to deserialize market book or no market book data found.");
        }
    }

    public async Task<List<MarketCatalogue>> ProcessGreyhoundMarketCataloguesAsync(string? targetEventId = null, string? competitionId = null)
{
    Console.WriteLine($"🔍 ProcessGreyhoundMarketCataloguesAsync called with eventId: {targetEventId}, competitionId: {competitionId}");
    
    var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId: targetEventId, competitionId: competitionId);
    Console.WriteLine($"📥 Market catalogue JSON response length: {marketCatalogueJson?.Length ?? 0}");
    
    var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

    if (marketCatalogueApiResponse == null)
    {
        Console.WriteLine("❌ Failed to deserialize the market catalogue JSON.");
        return new List<MarketCatalogue>();
    }
    else
    {
        Console.WriteLine($"✅ Deserialized Market Catalogue Result Count: {marketCatalogueApiResponse.Result?.Count()}");
    }

    if (marketCatalogueApiResponse?.Result == null || !marketCatalogueApiResponse.Result.Any())
    {
        Console.WriteLine("❌ No market catalogues found in response.");
        return new List<MarketCatalogue>();
    }

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
                : null,
            Runners = catalogue.Runners != null
                ? catalogue.Runners.Select(runner => new RunnerDescription
                {
                    SelectionId = runner.SelectionId,
                    RunnerName = runner.RunnerName,
                    Metadata = runner.Metadata
                }).ToList()
                : new List<RunnerDescription>()
        })
        .Where(catalogue => catalogue.Event != null)
        .ToList();

    var today = DateTime.Now.Date;
    var twoDaysFromNow = today.AddDays(2);
    var fourDaysAgo = today.AddDays(-4);  // Extended backwards for backfill

    Console.WriteLine($"🔍 Filtering {marketCatalogues.Count} market catalogues for eventId: {targetEventId}");
    Console.WriteLine($"🔍 Date range: {fourDaysAgo} to {twoDaysFromNow}");
    
    var filteredMarketCatalogues = marketCatalogues
        .Where(catalogue =>
        {
            var marketNameMatch = Regex.IsMatch(catalogue.MarketName, @"^R\d{1,2}");
            var hasOpenDate = catalogue.Event?.OpenDate.HasValue ?? false;
            var openDate = hasOpenDate ? catalogue.Event.OpenDate.Value.ToLocalTime().Date : DateTime.MinValue;
            var isWithinRange = hasOpenDate && openDate >= fourDaysAgo && openDate <= twoDaysFromNow;
            
            // Only filter by eventId if a specific one was requested, otherwise get all markets in date range
            var eventIdMatch = string.IsNullOrEmpty(targetEventId) || 
                             (catalogue.Event?.Id?.Equals(targetEventId, StringComparison.OrdinalIgnoreCase) ?? false);
            
            Console.WriteLine($"🔍 Market: {catalogue.MarketName}, EventId: {catalogue.Event?.Id}, Venue: {catalogue.Event?.Name}, MarketNameMatch: {marketNameMatch}, OpenDate: {openDate}, IsWithinRange: {isWithinRange}, EventIdMatch: {eventIdMatch}");
            
            return eventIdMatch && marketNameMatch && hasOpenDate && isWithinRange;
        })
        .ToList();

    Console.WriteLine($"🔍 Filtered to {filteredMarketCatalogues.Count} market catalogues");

    if (filteredMarketCatalogues.Any())
    {
        // FIRST: Cache runner names for use in market books processing
        foreach (var marketCatalogue in filteredMarketCatalogues)
        {
            if (marketCatalogue.Runners != null && marketCatalogue.Runners.Any())
            {
                var runnerMap = new Dictionary<long, string>();
                foreach (var runner in marketCatalogue.Runners)
                {
                    runnerMap[runner.SelectionId] = runner.RunnerName ?? $"Greyhound {runner.SelectionId}";
                }
                _runnerNamesCache[marketCatalogue.MarketId] = runnerMap;
                
                Console.WriteLine($"✅ Cached {runnerMap.Count} runner names for market {marketCatalogue.MarketId}");
            }
        }
        
        await _listMarketCatalogueDb.InsertMarketsIntoDatabase(filteredMarketCatalogues);
        
        // Also store in EventMarkets table for greyhound market book insertion
        foreach (var marketCatalogue in filteredMarketCatalogues)
        {
            if (marketCatalogue.Event != null && !string.IsNullOrEmpty(marketCatalogue.Event.Id))
            {
                var catalogueEventId = marketCatalogue.Event.Id;
                var eventName = marketCatalogue.Event.Name ?? "Unknown";
                await _eventDb.InsertEventMarketsAsync(catalogueEventId, eventName, new List<MarketCatalogue> { marketCatalogue });
            }
        }
    }
    else
    {
        //Console.WriteLine("No market catalogues to insert.");
    }

    return filteredMarketCatalogues;
}

}