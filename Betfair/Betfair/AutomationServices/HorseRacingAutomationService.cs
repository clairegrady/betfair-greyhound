using System.Text.Json;
using System.Text.RegularExpressions;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Services;

namespace Betfair.AutomationServices;

public class HorseRacingAutomationService
{
    private readonly IMarketApiService _marketApiService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;
    private readonly IEventService _eventService;

    public HorseRacingAutomationService(
        IMarketApiService marketApiService,
        ListMarketCatalogueDb listMarketCatalogueDb,
        MarketBookDb marketBookDb,
        IEventService eventService)
    {
        _marketApiService = marketApiService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
        _eventService = eventService;
    }

    public async Task<List<MarketCatalogue>> GetAndProcessHorseRacingMarketCataloguesAsync()
    {
        // Step 1: Get all event types
        var eventTypesJson = await _eventService.ListEventTypes();
        var eventTypesResponse = JsonSerializer.Deserialize<ApiResponse<EventTypeResult>>(eventTypesJson);

        var horseEventTypes = eventTypesResponse?.Result
            ?.Where(et => et.EventType.Name.Contains("horse", StringComparison.OrdinalIgnoreCase) ||
                          et.EventType.Name.Contains("racing", StringComparison.OrdinalIgnoreCase))
            .ToList();

        if (horseEventTypes == null || horseEventTypes.Count == 0)
        {
            Console.WriteLine("Horse racing event type not found.");
            return new List<MarketCatalogue>();
        }

        var horseEventTypeIds = horseEventTypes.Select(et => et.EventType.Id).ToList();

        // Step 2: Get current events for horse racing event types
        var eventsJson = await _eventService.ListEvents(horseEventTypeIds);
        var eventsResponse = JsonSerializer.Deserialize<ApiResponse<EventListResult>>(eventsJson);

        if (eventsResponse?.Result == null || !eventsResponse.Result.Any())
        {
            Console.WriteLine("No horse racing events found.");
            return new List<MarketCatalogue>();
        }

        var eventIds = eventsResponse.Result.Select(ev => ev.Event.Id).ToList();

        var allMarketCatalogues = new List<MarketCatalogue>();

        // Step 3: For each event, get market catalogues (optionally filter)
        foreach (var eventId in eventIds)
        {
            var marketCatalogueJson = await _marketApiService.ListHorseRacingMarketCatalogueAsync(eventId: eventId);
            var marketCatalogueResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

            if (marketCatalogueResponse?.Result == null || !marketCatalogueResponse.Result.Any())
            {
                Console.WriteLine($"No market catalogues found for event {eventId}.");
                continue;
            }

            var marketCatalogues = marketCatalogueResponse.Result
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
                            RunnerId = runner.RunnerId,
                            RunnerName = runner.RunnerName,
                            Metadata = runner.Metadata
                        }).ToList()
                        : new List<RunnerDescription>()
                })
                .Where(catalogue => catalogue.Event != null)
                .ToList();

            allMarketCatalogues.AddRange(marketCatalogues);
        }

        // Optional: insert into DB
        if (allMarketCatalogues.Any())
        {
            await _listMarketCatalogueDb.InsertMarketsIntoDatabase(allMarketCatalogues);
        }
        else
        {
            Console.WriteLine("No market catalogues to insert.");
        }

        return allMarketCatalogues;
    }

    public async Task ProcessHorseMarketBooksAsync(List<string> marketIds)
{
    if (marketIds == null || !marketIds.Any())
    {
        Console.WriteLine("No market IDs provided to process.");
        return;
    }

    try
    {
        // Call the API to get market book data for the given market IDs
        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);

        // Deserialize the JSON response into your ApiResponse wrapper
        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook>>(marketBookJson);

        if (marketBookApiResponse?.Result == null || !marketBookApiResponse.Result.Any())
        {
            Console.WriteLine("No market book data found for the provided market IDs.");
            return;
        }

        // Map the API results to your MarketBook entities
        var marketBooks = marketBookApiResponse.Result
            .Where(book => !string.IsNullOrEmpty(book.MarketId))
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

        if (marketBooks.Any())
        {
            // Insert the processed market books into the database
            await _marketBookDb.InsertHorseMarketBooksIntoDatabase(marketBooks);
            Console.WriteLine($"Inserted {marketBooks.Count} market books into the database.");
        }
        else
        {
            Console.WriteLine("No valid market books to insert.");
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"Error processing horse market books: {ex.Message}");
        // Consider logging or rethrowing as needed
    }
}

}
