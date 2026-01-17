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

        // Implement batch processing to avoid TOO_MUCH_DATA error
        const int batchSize = 10; // Start with 10 markets per batch to avoid Betfair limits
        var batches = marketIds
            .Select((marketId, index) => new { marketId, index })
            .GroupBy(x => x.index / batchSize)
            .Select(g => g.Select(x => x.marketId).ToList())
            .ToList();

        Console.WriteLine($"📦 Processing {marketIds.Count} markets in {batches.Count} batches of {batchSize}");

        var allMarketBooks = new List<MarketBook<ApiRunner>>();

        for (int i = 0; i < batches.Count; i++)
        {
            var batch = batches[i];
            //Console.WriteLine($"🔄 Processing batch {i + 1}/{batches.Count} with {batch.Count} markets");

            try
            {
                var marketBookJson = await _marketApiService.ListMarketBookAsync(batch);
                //Console.WriteLine($"📦 Batch {i + 1} - Received JSON: {(!string.IsNullOrEmpty(marketBookJson) ? $"Data received ({marketBookJson.Length} chars)" : "No data")}");

                // Check for error responses
                if (!string.IsNullOrEmpty(marketBookJson) && marketBookJson.Contains("\"error\""))
                {
                    Console.WriteLine($"⚠️ Batch {i + 1} - Error response detected: {marketBookJson}");
                    continue; // Skip this batch and continue with the next
                }

                var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
                Console.WriteLine($"🔄 Batch {i + 1} - Deserialization result: {marketBookApiResponse?.Result?.Count() ?? 0} market books");

                if (marketBookApiResponse?.Result?.Any() == true)
                {
                    var batchMarketBooks = marketBookApiResponse.Result
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

                    allMarketBooks.AddRange(batchMarketBooks);
                    Console.WriteLine($"✅ Batch {i + 1} - Added {batchMarketBooks.Count} market books (Total: {allMarketBooks.Count})");
                }
                else
                {
                    Console.WriteLine($"❌ Batch {i + 1} - No market books found in response");
                }

                // Add a small delay between batches to avoid rate limiting
                if (i < batches.Count - 1)
                {
                    await Task.Delay(100); // 100ms delay between batches
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Batch {i + 1} - Exception: {ex.Message}");
                // Continue with next batch instead of failing completely
            }
        }

        // Insert all collected market books into database
        if (allMarketBooks.Any())
        {
            Console.WriteLine($"📊 InsertMarketBooksIntoDatabase called with {allMarketBooks.Count} market books");
            await _marketBookDb.InsertMarketBooksIntoDatabase(allMarketBooks);
            Console.WriteLine($"✅ InsertMarketBooksIntoDatabase completed - {allMarketBooks.Count} market books processed");
        }
        else
        {
            Console.WriteLine("❌ No market books to insert after processing all batches");
        }
    }

   public async Task<List<MarketDetails>> ProcessMarketCataloguesAsync(string eventId = null, string competitionId = null)
{
    var marketCatalogueJson = await _marketApiService.ListMarketCatalogue(eventId: eventId, competitionId: competitionId);
    var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

    if (marketCatalogueApiResponse == null)
    {
        Console.WriteLine("Failed to deserialize the market catalogue JSON.");
    }
    else
    {
        Console.WriteLine($"Deserialized Result Count: {marketCatalogueApiResponse.Result?.Count()}");
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
        var tomorrow = today.AddDays(1);
        var fourDaysAgo = today.AddDays(-4);  // Extended backwards for backfill

        // Check each filter condition separately
        var eventIdMatches = marketCatalogues.Where(c => string.IsNullOrEmpty(eventId) || c.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase)).ToList();
        var raceNameMatches = marketCatalogues.Where(c => Regex.IsMatch(c.MarketName, @"^R\d{1,2}")).ToList();
        var hasOpenDate = marketCatalogues.Where(c => c.Event.OpenDate.HasValue).ToList();
        var todayEvents = marketCatalogues.Where(c => c.Event.OpenDate.HasValue && c.Event.OpenDate.Value.ToLocalTime().Date == today).ToList();
        var tomorrowEvents = marketCatalogues.Where(c => c.Event.OpenDate.HasValue && c.Event.OpenDate.Value.ToLocalTime().Date == tomorrow).ToList();
        var todayAndTomorrowEvents = marketCatalogues.Where(c => c.Event.OpenDate.HasValue &&
            (c.Event.OpenDate.Value.ToLocalTime().Date == today || c.Event.OpenDate.Value.ToLocalTime().Date == tomorrow)).ToList();

        Console.WriteLine($"Markets matching eventId filter: {eventIdMatches.Count}");
        Console.WriteLine($"Markets with race name pattern (R1, R2, etc.): {raceNameMatches.Count}");
        Console.WriteLine($"Markets with OpenDate: {hasOpenDate.Count}");
        Console.WriteLine($"Markets scheduled for today: {todayEvents.Count}");
        Console.WriteLine($"Markets scheduled for tomorrow: {tomorrowEvents.Count}");
        Console.WriteLine($"Markets scheduled for today or tomorrow: {todayAndTomorrowEvents.Count}");
        Console.WriteLine($"Extended date range for backfill: {fourDaysAgo} to {tomorrow}");

        // Modified filter to include last 4 days through tomorrow (for backfill)
        // Include both "RX" markets (WIN) and "To Be Placed" markets (PLACE)
        filteredMarketDetails = marketCatalogues
            .Where(catalogue => (string.IsNullOrEmpty(eventId) || catalogue.Event.Id.Equals(eventId, StringComparison.OrdinalIgnoreCase))
                                && (Regex.IsMatch(catalogue.MarketName, @"^R\d{1,2}") || 
                                    catalogue.MarketName.Contains("To Be Placed") || 
                                    catalogue.MarketName.Contains("TBP"))
                                && catalogue.Event.OpenDate.HasValue
                                && catalogue.Event.OpenDate.Value.ToLocalTime().Date >= fourDaysAgo
                                && catalogue.Event.OpenDate.Value.ToLocalTime().Date <= tomorrow)
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

    /// <summary>
    /// Process NCAA Basketball markets from Betfair
    /// Uses the basketball-specific ListBasketballMarketCatalogueAsync endpoint
    /// </summary>
    public async Task<List<MarketDetails>> ProcessNcaaBasketballMarketCataloguesAsync(string competitionId = null, string eventId = null)
    {
        Console.WriteLine($"🏀 ProcessNcaaBasketballMarketCataloguesAsync called - CompetitionId: {competitionId}, EventId: {eventId}");
        
        var marketCatalogueJson = await _marketApiService.ListBasketballMarketCatalogueAsync(competitionId, eventId);
        var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

        var filteredMarketDetails = new List<MarketDetails>();

        if (marketCatalogueApiResponse?.Result != null && marketCatalogueApiResponse.Result.Any())
        {
            Console.WriteLine($"🏀 Deserialized {marketCatalogueApiResponse.Result.Count()} NCAA Basketball markets");

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

            Console.WriteLine($"🏀 Mapped {marketCatalogues.Count} NCAA Basketball market catalogues");

            // Filter for Match Odds (Moneyline) markets - primary betting market for basketball
            var matchOddsMarkets = marketCatalogues
                .Where(catalogue => catalogue.MarketName.Contains("Match Odds", StringComparison.OrdinalIgnoreCase) ||
                                    catalogue.MarketName.Contains("Moneyline", StringComparison.OrdinalIgnoreCase))
                .ToList();

            Console.WriteLine($"🏀 Found {matchOddsMarkets.Count} Match Odds / Moneyline markets");

            // Create market details for return
            filteredMarketDetails = matchOddsMarkets
                .Select(catalogue => new MarketDetails
                {
                    MarketId = catalogue.MarketId,
                    MarketName = catalogue.MarketName
                })
                .ToList();

            // Insert all NCAA Basketball markets into database
            if (marketCatalogues.Any())
            {
                Console.WriteLine($"🏀 Inserting {marketCatalogues.Count} NCAA Basketball markets into database");
                await _listMarketCatalogueDb.InsertMarketsIntoDatabase(marketCatalogues);
                Console.WriteLine($"✅ Inserted NCAA Basketball markets into database");
            }
        }
        else
        {
            Console.WriteLine("🏀 No NCAA Basketball markets found or failed to deserialize");
        }

        Console.WriteLine($"🏀 Returning {filteredMarketDetails.Count} filtered NCAA Basketball market details");
        return filteredMarketDetails;
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