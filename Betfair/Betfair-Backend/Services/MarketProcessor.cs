using System.Text.Json;
using System.Text.RegularExpressions;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Competition;
using Betfair.Models.Event;
using Betfair.Models.Market;
using Betfair.Models.Runner;

namespace Betfair.Services;

public class MarketDetails
{
    public string MarketId { get; set; }
    public string MarketName { get; set; }
    // If you need EventName in MarketDetails for deconstruction or other purposes, add it as a property:
    public string EventName { get; set; }

    public void Deconstruct(out string marketName)
    {
        marketName = MarketName;
        // If EventName is added to MarketDetails, you can include it here:
        // eventName = EventName;
    }
}

public class MarketProcessor : IMarketProcessor
{
    private readonly IMarketApiService _marketApiService;
    private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
    private readonly MarketBookDb _marketBookDb;

    public MarketProcessor(IMarketApiService marketApiService, ListMarketCatalogueDb listMarketCatalogueDb, MarketBookDb marketBookDb)
    {
        _marketApiService = marketApiService;
        _listMarketCatalogueDb = listMarketCatalogueDb;
        _marketBookDb = marketBookDb;
    }

    public async Task ProcessMarketBooksAsync(List<string> marketIds)
    {
        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);
        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);

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
                        Status = runner.Status,
                        LastPriceTraded = runner.LastPriceTraded,
                        TotalMatched = runner.TotalMatched,
                        Handicap = runner.Handicap,

                        // Correctly map RunnerDescription and its nested Metadata
                        Description = runner.Description != null
                            ? new RunnerDescription
                            {
                                SelectionId = runner.Description.SelectionId,
                                RunnerName = runner.Description.RunnerName,
                                // Assuming Metadata can be directly assigned, as per your model
                                Metadata = runner.Description.Metadata != null
                                    ? new RunnerMetadata
                                    {
                                        Form = runner.Description.Metadata.Form,
                                        WeightValue = runner.Description.Metadata.WeightValue,
                                        StallDraw = runner.Description.Metadata.StallDraw,
                                        TrainerName = runner.Description.Metadata.TrainerName,
                                        OwnerName = runner.Description.Metadata.OwnerName,
                                        Age = runner.Description.Metadata.Age,
                                        SireName = runner.Description.Metadata.SireName,
                                        DamName = runner.Description.Metadata.DamName,
                                        Wearing = runner.Description.Metadata.Wearing,
                                        JockeyName = runner.Description.Metadata.JockeyName,
                                        JockeyClaim = runner.Description.Metadata.JockeyClaim,
                                        SexType = runner.Description.Metadata.SexType,
                                        DaysSinceLastRun = runner.Description.Metadata.DaysSinceLastRun,
                                        SireBred = runner.Description.Metadata.SireBred,
                                        DamBred = runner.Description.Metadata.DamBred,
                                        DamsireName = runner.Description.Metadata.DamsireName,
                                        DamsireBred = runner.Description.Metadata.DamsireBred,
                                        DamsireYearBorn = runner.Description.Metadata.DamsireYearBorn,
                                        SireYearBorn = runner.Description.Metadata.SireYearBorn,
                                        DamYearBorn = runner.Description.Metadata.DamYearBorn,
                                        AdjustedRating = runner.Description.Metadata.AdjustedRating,
                                        OfficialRating = runner.Description.Metadata.OfficialRating,
                                        ForecastPriceNumerator = runner.Description.Metadata.ForecastPriceNumerator,
                                        ForecastPriceDenominator = runner.Description.Metadata.ForecastPriceDenominator,
                                        Bred = runner.Description.Metadata.Bred,
                                        ColourType = runner.Description.Metadata.ColourType,
                                        WeightUnits = runner.Description.Metadata.WeightUnits,
                                        ClothNumber = runner.Description.Metadata.ClothNumber,
                                        ClothNumberAlpha = runner.Description.Metadata.ClothNumberAlpha,
                                        ColoursDescription = runner.Description.Metadata.ColoursDescription,
                                        ColoursFilename = runner.Description.Metadata.ColoursFilename,
                                        RunnerId = runner.Description.Metadata.RunnerId
                                    }
                                    : null
                            }
                            : null,

                        Exchange = runner.Exchange != null
                            ? new Exchange
                            {
                                AvailableToBack = runner.Exchange.AvailableToBack?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new List<PriceSize>(),
                                AvailableToLay = runner.Exchange.AvailableToLay?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new List<PriceSize>(),
                                TradedVolume = runner.Exchange.TradedVolume?.Select(p => new PriceSize { Price = p.Price, Size = p.Size }).ToList() ?? new List<PriceSize>()
                            }
                            : null,
                    }).ToList() ?? new List<ApiRunner>()
                })
                .ToList();

            if (marketBooks.Any())
            {
                await _marketBookDb.InsertMarketBooksIntoDatabase(marketBooks);
            }
            else
            {
                //Console.WriteLine("No market books to insert.");
            }
        }
        else
        {
            //Console.WriteLine("Failed to deserialize market book or no market book data found.");
        }
    }

    public async Task<List<MarketDetails>> ProcessMarketCataloguesAsync(string eventId = null, string competitionId = null)
    {
        var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
        //Console.WriteLine("Raw Market Catalogue JSON:");
        //Console.WriteLine(marketCatalogueJson);
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
                            // Reconstruct Metadata fully if needed, based on your RunnerMetadata model
                            Metadata = runner.Metadata != null
                                ? new RunnerMetadata
                                {
                                    Form = runner.Metadata.Form,
                                    WeightValue = runner.Metadata.WeightValue,
                                    StallDraw = runner.Metadata.StallDraw,
                                    TrainerName = runner.Metadata.TrainerName,
                                    OwnerName = runner.Metadata.OwnerName,
                                    Age = runner.Metadata.Age,
                                    SireName = runner.Metadata.SireName,
                                    DamName = runner.Metadata.DamName,
                                    Wearing = runner.Metadata.Wearing,
                                    JockeyName = runner.Metadata.JockeyName,
                                    JockeyClaim = runner.Metadata.JockeyClaim,
                                    SexType = runner.Metadata.SexType,
                                    DaysSinceLastRun = runner.Metadata.DaysSinceLastRun,
                                    SireBred = runner.Metadata.SireBred,
                                    DamBred = runner.Metadata.DamBred,
                                    DamsireName = runner.Metadata.DamsireName,
                                    DamsireBred = runner.Metadata.DamsireBred,
                                    DamsireYearBorn = runner.Metadata.DamsireYearBorn,
                                    SireYearBorn = runner.Metadata.SireYearBorn,
                                    DamYearBorn = runner.Metadata.DamYearBorn,
                                    AdjustedRating = runner.Metadata.AdjustedRating,
                                    OfficialRating = runner.Metadata.OfficialRating,
                                    ForecastPriceNumerator = runner.Metadata.ForecastPriceNumerator,
                                    ForecastPriceDenominator = runner.Metadata.ForecastPriceDenominator,
                                    Bred = runner.Metadata.Bred,
                                    ColourType = runner.Metadata.ColourType,
                                    WeightUnits = runner.Metadata.WeightUnits,
                                    ClothNumber = runner.Metadata.ClothNumber,
                                    ClothNumberAlpha = runner.Metadata.ClothNumberAlpha,
                                    ColoursDescription = runner.Metadata.ColoursDescription,
                                    ColoursFilename = runner.Metadata.ColoursFilename,
                                    RunnerId = runner.Metadata.RunnerId
                                }
                                : null
                        }).ToList()
                        : new List<RunnerDescription>()
                })
                .Where(catalogue => catalogue.Event != null)
                .ToList();

            var today = DateTime.Now.Date;
            filteredMarketDetails = marketCatalogues
                .Where(catalogue =>
                    !string.IsNullOrEmpty(catalogue.Event?.Id) &&
                    catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase) &&
                    Regex.IsMatch(catalogue.MarketName, @"^R\d{1,2}") &&
                    catalogue.Event.OpenDate.HasValue &&
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
                    Runners = catalogue.Runners != null
                        ? catalogue.Runners.Select(runner => new RunnerDescription
                        {
                            SelectionId = runner.SelectionId,
                            RunnerName = runner.RunnerName,
                            Metadata = runner.Metadata != null
                                ? new RunnerMetadata
                                {
                                    Form = runner.Metadata.Form,
                                    WeightValue = runner.Metadata.WeightValue,
                                    StallDraw = runner.Metadata.StallDraw,
                                    TrainerName = runner.Metadata.TrainerName,
                                    OwnerName = runner.Metadata.OwnerName,
                                    Age = runner.Metadata.Age,
                                    SireName = runner.Metadata.SireName,
                                    DamName = runner.Metadata.DamName,
                                    Wearing = runner.Metadata.Wearing,
                                    JockeyName = runner.Metadata.JockeyName,
                                    JockeyClaim = runner.Metadata.JockeyClaim,
                                    SexType = runner.Metadata.SexType,
                                    DaysSinceLastRun = runner.Metadata.DaysSinceLastRun,
                                    SireBred = runner.Metadata.SireBred,
                                    DamBred = runner.Metadata.DamBred,
                                    DamsireName = runner.Metadata.DamsireName,
                                    DamsireBred = runner.Metadata.DamsireBred,
                                    DamsireYearBorn = runner.Metadata.DamsireYearBorn,
                                    SireYearBorn = runner.Metadata.SireYearBorn,
                                    DamYearBorn = runner.Metadata.DamYearBorn,
                                    AdjustedRating = runner.Metadata.AdjustedRating,
                                    OfficialRating = runner.Metadata.OfficialRating,
                                    ForecastPriceNumerator = runner.Metadata.ForecastPriceNumerator,
                                    ForecastPriceDenominator = runner.Metadata.ForecastPriceDenominator,
                                    Bred = runner.Metadata.Bred,
                                    ColourType = runner.Metadata.ColourType,
                                    WeightUnits = runner.Metadata.WeightUnits,
                                    ClothNumber = runner.Metadata.ClothNumber,
                                    ClothNumberAlpha = runner.Metadata.ClothNumberAlpha,
                                    ColoursDescription = runner.Metadata.ColoursDescription,
                                    ColoursFilename = runner.Metadata.ColoursFilename,
                                    RunnerId = runner.Metadata.RunnerId
                                }
                                : null
                        }).ToList()
                        : new List<RunnerDescription>()
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

public interface IMarketProcessor
{
    Task ProcessMarketBooksAsync(List<string> marketIds);
    Task<List<MarketDetails>> ProcessMarketCataloguesAsync(string eventId = null, string competitionId = null);
    Task<List<string>> ProcessNbaMarketCataloguesAsync(string eventId);
    Task FetchAndStoreMarketProfitAndLossAsync(List<string> marketIds);
}