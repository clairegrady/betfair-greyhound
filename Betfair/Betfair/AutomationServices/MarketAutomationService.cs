using System.Text.Json;
using System.Text.RegularExpressions;
using Betfair.Data;
using Betfair.Mappers;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Betfair.Services;

namespace Betfair.AutomationServices;

public class MarketDetails
{
    public string MarketId { get; set; }
    public string MarketName { get; set; }
}

public class MarketAutomationService
{
    private readonly IMarketApiService _marketApiService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;

    public MarketAutomationService(IMarketApiService marketApiService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb)
    {
        _marketApiService = marketApiService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
    }

    public async Task ProcessMarketBooksAsync(List<string> marketIds)
    {
        Console.WriteLine($"🎯 ProcessMarketBooksAsync called with {marketIds?.Count ?? 0} market IDs");

        if (marketIds == null || !marketIds.Any())
        {
            Console.WriteLine("❌ No market IDs provided to ProcessMarketBooksAsync - returning early");
            return;
        }

        Console.WriteLine($"🔍 Market IDs to process: [{string.Join(", ", marketIds)}]");

        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);
        Console.WriteLine($"📦 Received market book JSON: {(!string.IsNullOrEmpty(marketBookJson) ? "Data received" : "No data")}");

        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
        Console.WriteLine($"🔄 Deserialization result: {marketBookApiResponse?.Result?.Count() ?? 0} market books");

        if (marketBookApiResponse?.Result?.Any() == true)
        {
            var marketBooks = marketBookApiResponse.Result
                .Where(book => book.MarketId != null)
                .Select(book => new MarketBook<ApiRunner>
                {
                    MarketId = book.MarketId,
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
                        Handicap = runner.Handicap,
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
                        Description = runner.Description
                    }).ToList() ?? new List<ApiRunner>()
                })
                .ToList();

            Console.WriteLine($"🏆 Processed {marketBooks.Count} market books with exchange data");

            // Log details about exchange data
            foreach (var book in marketBooks)
            {
                var runnersWithExchange = book.Runners?.Count(r => r.Exchange != null) ?? 0;
                var totalBackPrices = book.Runners?.Sum(r => r.Exchange?.AvailableToBack?.Count ?? 0) ?? 0;
                var totalLayPrices = book.Runners?.Sum(r => r.Exchange?.AvailableToLay?.Count ?? 0) ?? 0;

                Console.WriteLine($"📈 Market {book.MarketId}: {runnersWithExchange} runners with exchange data, {totalBackPrices} back prices, {totalLayPrices} lay prices");
            }

            if (marketBooks.Any())
            {
                Console.WriteLine($"💾 Calling InsertMarketBooksIntoDatabase with {marketBooks.Count} market books");
                await _marketBookDb.InsertMarketBooksIntoDatabase(marketBooks);
                Console.WriteLine($"✅ InsertMarketBooksIntoDatabase completed");
            }
            else
            {
                Console.WriteLine("❌ No market books to insert after processing");
            }
        }
        else
        {
            Console.WriteLine("❌ Failed to deserialize market book or no market book data found");
        }
    }

   public async Task<List<MarketDetails>> ProcessMarketCataloguesAsync(string eventId = null, string competitionId = null)
{
    var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
    var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

    if (marketCatalogueApiResponse == null)
    {
        //Console.WriteLine("Failed to deserialize the market catalogue JSON.");
    }
    else
    {
        //Console.WriteLine($"Deserialized Result Count: {marketCatalogueApiResponse.Result?.Count()}");
    }

    var filteredMarketDetails = new List<MarketDetails>();

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

        // Flatten all runners from all market catalogues using RunnerMapper
        var allFlatRunners = marketCatalogues
            .SelectMany(mc => mc.Runners)
            .Select(runnerDesc => RunnerMapper.MapToFlat(runnerDesc))
            .ToList();

        //Console.WriteLine($"Total runners flattened: {allFlatRunners.Count}");

        // TODO: Insert flattened runners into database if you have a runner DB
        // await _runnerDb.InsertRunnersAsync(allFlatRunners);

        var today = DateTime.Now.Date;
        filteredMarketDetails = marketCatalogues
            .Where(catalogue => catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase)
                                && Regex.IsMatch(catalogue.MarketName, @"^R\d{1,2}")
                                && catalogue.Event.OpenDate.HasValue
                                && catalogue.Event.OpenDate.Value.ToLocalTime().Date == today)
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
            //Console.WriteLine("No market catalogues to insert.");
        }
    }
    else
    {
        //Console.WriteLine("Failed to deserialize market catalogues or no market catalogues found.");
    }

    return filteredMarketDetails;
}


    public async Task<List<string>> ProcessNbaMarketCataloguesAsync(string eventId)
    {
        var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId);
        var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

        var filteredMarketIds = new List<string>();

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
                        : null,
                    Runners = catalogue.Runners?.Select(runner => new RunnerDescription
                    {
                        SelectionId = runner.SelectionId,
                        RunnerName = runner.RunnerName,
                        Metadata = runner.Metadata
                    }).ToList()
                        ?? new List<RunnerDescription>()
                })
                .Where(catalogue => catalogue.Event != null)
                .ToList();

            filteredMarketIds = marketCatalogues
                .Where(catalogue => catalogue.MarketName.Contains("Moneyline", StringComparison.OrdinalIgnoreCase))
                .Select(catalogue => catalogue.MarketId)
                .ToList();

            if (marketCatalogues.Any())
            {
                await _listMarketCatalogueDb.InsertMarketsIntoDatabase(marketCatalogues);
            }
            else
            {
                //Console.WriteLine("No market catalogues to insert.");
            }
        }
        else
        {
            //Console.WriteLine("Failed to deserialize market catalogues or no market catalogues found.");
        }

        //Console.WriteLine($"Filtered Market Ids: {filteredMarketIds.Count}");
        return filteredMarketIds;
    }

    public async Task FetchAndStoreMarketProfitAndLossAsync(List<string> marketIds)
    {
        try
        {
            await _marketApiService.ProcessAndStoreMarketProfitAndLoss(marketIds);

            //Console.WriteLine("Market Profit and Loss data fetched and stored successfully.");
        }
        catch (Exception ex)
        {
            //Console.WriteLine($"Failed to fetch and store Market Profit and Loss data: {ex.Message}");
        }
    }
}