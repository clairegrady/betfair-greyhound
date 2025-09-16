using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization; 
using System.Threading.Tasks; 
using Betfair.Data; 
using Betfair.Models; 
using Betfair.Models.Market; 
using Betfair.Models.Runner; 
using Betfair.Services;

namespace Betfair.AutomationServices
{

    public class HorseRacingAutomationService
    {
        private readonly IMarketApiService _marketApiService;
        private readonly ListMarketCatalogueDb _listMarketCatalogueDb;
        private readonly MarketBookDb _marketBookDb;
        private readonly IEventService _eventService;

        // New field to store runner descriptions for lookup
        private Dictionary<long, RunnerDescription> _runnerDescriptionsLookup;
        private Dictionary<string, MarketCatalogue> _marketCatalogueLookup = new();

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

            // Initialize the lookup dictionary
            _runnerDescriptionsLookup = new Dictionary<long, RunnerDescription>();
            _marketCatalogueLookup = new Dictionary<string, MarketCatalogue>();
        }

        public async Task<List<MarketCatalogue>> GetAndProcessHorseRacingMarketCataloguesAsync(string eventId = null)
        {
            var today = DateTime.UtcNow.Date;
            var marketCatalogueJson =
                await _marketApiService.ListHorseRacingMarketCatalogueAsync(eventTypeId: "7", openDate: today);
            Console.WriteLine($"JSON length: {marketCatalogueJson?.Length ?? 0} characters");

            // Check for Australian/NZ venues in the raw JSON
            if (marketCatalogueJson?.Contains("AUS") == true)
            {
                Console.WriteLine("✅ Found 'AUS' in raw JSON");
            }

            if (marketCatalogueJson?.Contains("NZ") == true)
            {
                Console.WriteLine("✅ Found 'NZ' in raw JSON");
            }

            ApiResponse<MarketCatalogue> apiResponse;

            try
            {
                var options = new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true,
                    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
                    AllowTrailingCommas = true
                };

                // Deserialize the overall API response wrapper with the specified options
                apiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson, options);

                if (apiResponse?.Result != null)
                {
                    Console.WriteLine(
                        $"Market catalogues received (apiResponse.Result.Count): {apiResponse.Result.Count}");

                    var marketIds = apiResponse.Result.Select(market => market.MarketId).ToList();
                    var ausNzMarkets = marketIds.Where(id => id.StartsWith("1.2468") || id.StartsWith("1.2469"))
                        .ToList();
                    Console.WriteLine($"🇦🇺🇳🇿 Australian/NZ markets found: {ausNzMarkets.Count}");
                    if (ausNzMarkets.Any())
                    {
                        Console.WriteLine($"   Sample AUS/NZ market IDs: {string.Join(", ", ausNzMarkets.Take(5))}");
                    }
                }
            }
            catch (JsonException ex)
            {
                return new List<MarketCatalogue>();
            }
            catch (Exception ex)
            {
                return new List<MarketCatalogue>();
            }

            var marketCatalogues = apiResponse?.Result ?? new List<MarketCatalogue>();

            _marketCatalogueLookup = marketCatalogues
                .Where(mc => !string.IsNullOrEmpty(mc.MarketId))
                .ToDictionary(mc => mc.MarketId, mc => mc);

            if (marketCatalogues.Any())
            {
                foreach (var market in marketCatalogues.Take(2))
                {

                    if (market.Runners != null)
                    {
                        foreach (var runnerDescription in market.Runners.Take(3))
                        {
                            var metadata = runnerDescription.Metadata;
                            if (metadata != null)
                            {
                                // This output should now show actual values, confirming Metadata is populated
                                //Console.WriteLine($"      Form: '{metadata.Form ?? "NULL"}'");
                                //Console.WriteLine($"      SireName: '{metadata.SireName ?? "NULL"}'");
                                //Console.WriteLine($"      Bred: '{metadata.Bred ?? "NULL"}'");
                                //Console.WriteLine($"      JockeyClaim: '{metadata.JockeyClaim ?? "NULL"}'"); // Check nulls here
                                //Console.WriteLine($"      OfficialRating: '{metadata.OfficialRating ?? "NULL"}'"); // Check nulls here
                            }
                            else
                            {
                                //Console.WriteLine($"      No Metadata available for Runner: {runnerDescription.RunnerName}");
                            }
                        }
                    }
                }
                //Console.WriteLine("--- Finished Market Catalogue Content Verification ---");

                // Populate the lookup dictionary after successful catalogue retrieval
                PopulateRunnerDescriptionsLookup(marketCatalogues);
            }

            return marketCatalogues;
        }

        public void PopulateRunnerDescriptionsLookup(List<MarketCatalogue> marketCatalogues)
        {
            _runnerDescriptionsLookup.Clear();

            foreach (var marketCatalogue in marketCatalogues)
            {
                if (marketCatalogue.Runners != null)
                {
                    foreach (var runnerDescription in marketCatalogue.Runners)
                    {
                        if (!_runnerDescriptionsLookup.ContainsKey(runnerDescription.SelectionId))
                        {
                            _runnerDescriptionsLookup.Add(runnerDescription.SelectionId, runnerDescription);
                        }
                    }
                }
            }

            //Console.WriteLine(
                //$"Populated RunnerDescriptionsLookup with {_runnerDescriptionsLookup.Count} unique runners.");
        }

        public async Task<List<RunnerFlat>> ProcessHorseMarketBooksAsync(List<string> marketIds)
        {
            if (marketIds == null || !marketIds.Any())
            {
                return new List<RunnerFlat>();
            }

            try
            {
                // Step 1: Fetch and deserialize MarketBook JSON in batches
                Console.WriteLine($"📞 Processing {marketIds.Count} market IDs in batches of 10");

                var allMarketBooks = new List<MarketBook<ApiRunner>>();
                const int batchSize = 10;

                // Process all batches first, accumulating results
                for (int i = 0; i < marketIds.Count; i += batchSize)
                {
                    var batch = marketIds.Skip(i).Take(batchSize).ToList();
                    Console.WriteLine($"📦 Processing batch {i / batchSize + 1}: {batch.Count} markets");

                    var marketBookJson = await _marketApiService.ListMarketBookAsync(batch);

                    Console.WriteLine($"📥 Batch {i / batchSize + 1} Response: {marketBookJson?.Length ?? 0} characters");
                    if (marketBookJson?.Contains("error") == true)
                    {
                        Console.WriteLine($"❌ Batch {i / batchSize + 1} Error: {marketBookJson}");
                        continue;
                    }

                    var batchResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
                    if (batchResponse?.Result != null)
                    {
                        allMarketBooks.AddRange(batchResponse.Result);
                        Console.WriteLine($"✅ Batch {i / batchSize + 1}: Added {batchResponse.Result.Count} markets");
                    }
                }

                Console.WriteLine($"📊 Total markets collected: {allMarketBooks.Count}");

                // Now process all accumulated market books
                if (!allMarketBooks.Any())
                {
                    Console.WriteLine("❌ No market books collected from any batch");
                    return new List<RunnerFlat>();
                }

                var marketBookApiResponse = new ApiResponse<MarketBook<ApiRunner>> { Result = allMarketBooks };
                Console.WriteLine($"📊 JSON Analysis: Received {marketBookApiResponse?.Result?.Count ?? 0} markets from API");

                if (marketBookApiResponse?.Result != null)
                {
                    var marketCounts = marketBookApiResponse.Result
                        .GroupBy(m => m.MarketId?.Split('.')[0] ?? "Unknown")
                        .Select(g => new { MarketId = g.Key, Count = g.Count() })
                        .ToList();

                    Console.WriteLine($"🌍 Market breakdown: {string.Join(", ", marketCounts.Select(m => $"{m.MarketId}:{m.Count}"))}");
                }

                // Step 2: Flatten MarketBooks to RunnerFlat objects, COMBINING with catalogue data
                Console.WriteLine("🔄 Starting to flatten market books to RunnerFlat objects...");
                var flattenedMarketBooks = marketBookApiResponse.Result
                    .Where(book => !string.IsNullOrEmpty(book.MarketId))
                    .Select(book => new MarketBook<RunnerFlat>
                    {
                        MarketId = book.MarketId,
                        Status = book.Status,
                        BetDelay = book.BetDelay,
                        LastMatchTime = book.LastMatchTime,
                        TotalMatched = book.TotalMatched,
                        Runners = book.Runners?.Select(apiRunner =>
                        {
                            RunnerDescription? runnerDescriptionFromCatalogue = null;
                            bool foundInLookup = _runnerDescriptionsLookup.TryGetValue(apiRunner.SelectionId, out runnerDescriptionFromCatalogue);

                            // Safely get metadata and runner name from the catalogue description
                            var metadata = runnerDescriptionFromCatalogue?.Metadata ?? new RunnerMetadata();
                            var runnerName = runnerDescriptionFromCatalogue?.RunnerName;

                            return new RunnerFlat
                            {
                                // From MarketBook API
                                SelectionId = apiRunner.SelectionId,
                                Handicap = apiRunner.Handicap,
                                Status = apiRunner.Status,
                                LastPriceTraded = apiRunner.LastPriceTraded,
                                TotalMatched = apiRunner.TotalMatched,

                                RunnerName = runnerName, // From Market Catalogue Description

                                // Metadata fields from Market Catalogue Description
                                Form = metadata.Form,
                                WeightValue = metadata.WeightValue,
                                StallDraw = metadata.StallDraw,
                                TrainerName = metadata.TrainerName,
                                OwnerName = metadata.OwnerName,
                                Age = metadata.Age,
                                SireName = metadata.SireName,
                                DamName = metadata.DamName,
                                Wearing = metadata.Wearing,
                                JockeyName = metadata.JockeyName,
                                JockeyClaim = metadata.JockeyClaim,
                                SexType = metadata.SexType,
                                DaysSinceLastRun = metadata.DaysSinceLastRun,
                                SireBred = metadata.SireBred,
                                DamBred = metadata.DamBred,
                                DamsireName = metadata.DamsireName,
                                DamsireBred = metadata.DamsireBred,
                                DamsireYearBorn = metadata.DamsireYearBorn,
                                SireYearBorn = metadata.SireYearBorn,
                                DamYearBorn = metadata.DamYearBorn,
                                AdjustedRating = metadata.AdjustedRating,
                                OfficialRating = metadata.OfficialRating,
                                ForecastPriceNumerator = metadata.ForecastPriceNumerator,
                                ForecastPriceDenominator = metadata.ForecastPriceDenominator,
                                Bred = metadata.Bred,
                                ColourType = metadata.ColourType,
                                WeightUnits = metadata.WeightUnits,
                                ClothNumber = metadata.ClothNumber,
                                ClothNumberAlpha = metadata.ClothNumberAlpha,
                                ColoursDescription = metadata.ColoursDescription,
                                ColoursFilename = metadata.ColoursFilename,
                                MetadataRunnerId = metadata.RunnerId,
                            };
                        }).ToList()
                    }).ToList();

                if (flattenedMarketBooks.Any())
                {
                    int totalRunnersToInsert = 0;
                    foreach (var marketBookFlat in flattenedMarketBooks)
                    {
                        if (marketBookFlat.Runners != null)
                        {
                            totalRunnersToInsert += marketBookFlat.Runners.Count;
                        }
                    }

                    Console.WriteLine($"📈 Flattening complete: {flattenedMarketBooks.Count} markets processed out of {marketBookApiResponse?.Result?.Count ?? 0} received, with {totalRunnersToInsert} total runners");

                    await _marketBookDb.InsertHorseMarketBooksIntoDatabase(flattenedMarketBooks);

                    // NEW: Also insert the betting prices for the same markets
                    Console.WriteLine("🎯 Also inserting back/lay prices for the same horse racing markets...");
                    var apiRunnerMarketBooks = marketBookApiResponse.Result.ToList();
                    await _marketBookDb.InsertMarketBooksIntoDatabase(apiRunnerMarketBooks);
                    Console.WriteLine("✅ Back/lay prices insertion completed for horse racing markets");

                    Console.WriteLine("ProcessHorseMarketBooksAsync: InsertHorseMarketBooksIntoDatabase call completed.");
                }

                var allFlattenedRunners = flattenedMarketBooks.SelectMany(marketBook => marketBook.Runners).ToList();
                return allFlattenedRunners;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Error in ProcessHorseMarketBooksAsync: {ex.Message}");
                return new List<RunnerFlat>();
            }
        }
    }
}