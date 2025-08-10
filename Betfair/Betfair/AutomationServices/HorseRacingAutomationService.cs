using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization; // Required for [JsonPropertyName]
using System.Threading.Tasks; // Required for async/await

// Assuming these namespaces are correct for your models and services
using Betfair.Data; // For ListMarketCatalogueDb, MarketBookDb
using Betfair.Models; // For ApiResponse
using Betfair.Models.Market; // For MarketBook, MarketCatalogue
using Betfair.Models.Runner; // For ApiRunner, RunnerDescription, RunnerFlat, RunnerMetadata
using Betfair.Services; // For IMarketApiService, IEventService

namespace Betfair.AutomationServices
{
    // --- START: Models (Ensuring they are correctly defined with JsonPropertyName) ---
    // You should have these in their respective files (e.g., Models/Runner/RunnerFlat.cs, Models/Runner/RunnerMetadata.cs)
    // I'm including them here for completeness based on our discussion, but put them in their proper files.

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

        // Method 1: GetAndProcessHorseRacingMarketCataloguesAsync (fetches descriptions)
        public async Task<List<MarketCatalogue>> GetAndProcessHorseRacingMarketCataloguesAsync(string eventId = null)
        {
            var today = DateTime.UtcNow.Date;

            //Console.WriteLine($"--- GetAndProcessHorseRacingMarketCataloguesAsync: Fetching Market Catalogues for today ({today:yyyy-MM-dd}) ---");
            var marketCatalogueJson = await _marketApiService.ListHorseRacingMarketCatalogueAsync(eventTypeId: "7", openDate: today);

            Console.WriteLine("--- Raw Market Catalogue JSON (full) ---");
            Console.WriteLine(marketCatalogueJson);

            //Console.WriteLine("--- Raw Market Catalogue JSON (first 500 chars) ---");
            //Console.WriteLine(marketCatalogueJson.Substring(0, Math.Min(500, marketCatalogueJson.Length)));

            //Console.WriteLine("--- Attempting Deserialization of Market Catalogue ---");

            ApiResponse<MarketCatalogue> apiResponse;

            try
            {
                // Define JsonSerializerOptions to handle case-insensitivity, ignore nulls, and allow trailing commas
                var options = new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true,  // Handle case-insensitive property names
                    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull, // Ignore nulls
                    AllowTrailingCommas = true  // Allow trailing commas in JSON
                };

                // Deserialize the overall API response wrapper with the specified options
                apiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson, options);

               //Console.WriteLine($"Deserialization successful. Market Catalogue API Response Result property is {(apiResponse?.Result != null ? "not null" : "null")}.");

                if (apiResponse?.Result != null)
                {
                   //Console.WriteLine($"Market catalogues received (apiResponse.Result.Count): {apiResponse.Result.Count}");
                }
            }
            catch (JsonException ex)
            {
                // Handle JSON parsing errors (log, rethrow, etc.)
               //Console.WriteLine($"JSON Deserialization ERROR for Market Catalogue: {ex.Message}");
               //Console.WriteLine($"JSON Path: {ex.Path}, LineNumber: {ex.LineNumber}, BytePositionInLine: {ex.BytePositionInLine}");
                return new List<MarketCatalogue>(); // Return empty list on deserialization error
            }
            catch (Exception ex)
            {
                // Handle other types of exceptions
               //Console.WriteLine($"General Deserialization ERROR for Market Catalogue: {ex.Message}");
                return new List<MarketCatalogue>(); // Return empty list on other errors
            }

            var marketCatalogues = apiResponse?.Result ?? new List<MarketCatalogue>();

            _marketCatalogueLookup = marketCatalogues
                .Where(mc => !string.IsNullOrEmpty(mc.MarketId))
                .ToDictionary(mc => mc.MarketId, mc => mc);

           //Console.WriteLine($"Final processed market catalogues count: {marketCatalogues.Count}");

            if (marketCatalogues.Any())
            {
               //Console.WriteLine("--- Verifying Market Catalogue Contents (Post-Deserialization) ---");
                foreach (var market in marketCatalogues.Take(2)) // Print details for first 2 markets
                {
                   //Console.WriteLine($"\nMarket Id: {market.MarketId}, Market Name: {market.MarketName}, Event: {market.Event?.Name}");

                    if (market.Runners != null)
                    {
                       //Console.WriteLine($"  Runners in this Market: {market.Runners.Count}");
                        foreach (var runnerDescription in market.Runners.Take(3)) // Print first 3 runners per market
                        {
                            var metadata = runnerDescription.Metadata;
                           //Console.WriteLine($"    Runner Name: {runnerDescription.RunnerName}");
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
            else
            {
               //Console.WriteLine("No market catalogues found.");
            }
            return marketCatalogues;
        }

        // Method to populate the lookup dictionary (called internally)
        public void PopulateRunnerDescriptionsLookup(List<MarketCatalogue> marketCatalogues)
        {
            _runnerDescriptionsLookup.Clear(); // Clear any previous data

            foreach (var marketCatalogue in marketCatalogues)
            {
                if (marketCatalogue.Runners != null)
                {
                    foreach (var runnerDescription in marketCatalogue.Runners)
                    {
                        // Log the metadata for debugging purposes
                        Console.WriteLine($"Runner SelectionId: {runnerDescription.SelectionId}, OwnerName: {runnerDescription.Metadata?.OwnerName}");

                        // Use SelectionId as the key for lookup
                        if (!_runnerDescriptionsLookup.ContainsKey(runnerDescription.SelectionId))
                        {
                            _runnerDescriptionsLookup.Add(runnerDescription.SelectionId, runnerDescription);
                        }
                    }
                }
            }
            Console.WriteLine($"Populated RunnerDescriptionsLookup with {_runnerDescriptionsLookup.Count} unique runners.");
        }


        // Method 2: ProcessHorseMarketBooksAsync (fetches prices/status and combines with descriptions)
       // Inside HorseRacingAutomationService.cs
public async Task<List<RunnerFlat>> ProcessHorseMarketBooksAsync(List<string> marketIds)
{
   //Console.WriteLine($"--- Starting ProcessHorseMarketBooksAsync for {marketIds.Count} market IDs ---");

    if (marketIds == null || !marketIds.Any())
    {
       //Console.WriteLine("ProcessHorseMarketBooksAsync: No market IDs provided or list is null.");
        return new List<RunnerFlat>();
    }

    // Important: Check if lookup data is available
    if (!_runnerDescriptionsLookup.Any())
    {
       //Console.WriteLine("ProcessHorseMarketBooksAsync: Runner descriptions lookup is empty. Ensure GetAndProcessHorseRacingMarketCataloguesAsync was called and populated it.");
        // This is a critical warning. If the lookup is empty, all metadata will be null.
        // You might want to throw an exception or return an empty list here if having metadata is mandatory.
    }
    else
    {
       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Runner descriptions lookup contains {_runnerDescriptionsLookup.Count} unique runners.");
    }


    try
    {
        // Step 1: Fetch and deserialize MarketBook JSON
       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Calling ListMarketBookAsync for {marketIds.Count} market IDs.");
        var marketBookJson = await _marketApiService.ListMarketBookAsync(marketIds);
       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Received MarketBook JSON. Length: {marketBookJson?.Length ?? 0}.");

        // Print a sample of the MarketBook JSON
       //Console.WriteLine("--- MarketBook JSON Sample (first 500 chars) ---");
       //Console.WriteLine(marketBookJson?.Substring(0, Math.Min(500, marketBookJson.Length)) ?? "NULL JSON received");
       //Console.WriteLine("---------------------------------------------");


        var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);
       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Deserialized MarketBook API Response. Result count: {marketBookApiResponse?.Result?.Count ?? 0}.");

        if (marketBookApiResponse?.Result == null || !marketBookApiResponse.Result.Any())
        {
           //Console.WriteLine("ProcessHorseMarketBooksAsync: No market book results found after deserialization.");
            return new List<RunnerFlat>();
        }

        // Step 2: Flatten MarketBooks to RunnerFlat objects, COMBINING with catalogue data
       //Console.WriteLine("ProcessHorseMarketBooksAsync: Starting to flatten market books to RunnerFlat.");
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
                    // Attempt to get the RunnerDescription from the pre-populated lookup
                    RunnerDescription? runnerDescriptionFromCatalogue = null;
                    bool foundInLookup = _runnerDescriptionsLookup.TryGetValue(apiRunner.SelectionId, out runnerDescriptionFromCatalogue);

                    // Safely get metadata and runner name from the catalogue description
                    // If not found in catalogue, metadata and runnerName will remain null.
                    var metadata = runnerDescriptionFromCatalogue?.Metadata ?? new RunnerMetadata(); // If description is null, default to empty metadata
                    var runnerName = runnerDescriptionFromCatalogue?.RunnerName;

                    // *** NEW LOGGING HERE ***
                   //Console.WriteLine($"  Processing Runner: {apiRunner.SelectionId}. Found in lookup: {foundInLookup}");
                    if (foundInLookup)
                    {
                       //Console.WriteLine($"    Catalogue Data: Name='{runnerName ?? "NULL"}', Form='{metadata.Form ?? "NULL"}', JockeyClaim='{metadata.JockeyClaim ?? "NULL"}'");
                    }
                    else
                    {
                       //Console.WriteLine($"    WARNING: No catalogue description found for SelectionId: {apiRunner.SelectionId}. Metadata will be null.");
                    }
                    // *** END NEW LOGGING ***

                    return new RunnerFlat
                    {
                        SelectionId = apiRunner.SelectionId,
                        Handicap = apiRunner.Handicap,
                        Status = apiRunner.Status, // From MarketBook API
                        LastPriceTraded = apiRunner.LastPriceTraded, // From MarketBook API
                        TotalMatched = apiRunner.TotalMatched, // From MarketBook API

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

       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Finished flattening. Total flattened market books: {flattenedMarketBooks.Count}.");

        // Step 3: Insert into Database
        if (flattenedMarketBooks.Any())
        {
           //Console.WriteLine("--- VERIFYING flattenedMarketBooks contents before DB insertion ---");
            int totalRunnersToInsert = 0;
            // Iterate all flattened market books to get the total count
            foreach (var marketBookFlat in flattenedMarketBooks)
            {
                if (marketBookFlat.Runners != null)
                {
                    totalRunnersToInsert += marketBookFlat.Runners.Count;
                }
            }

            // Limit print to first 5 market books for detailed check, but report total
            foreach (var marketBookFlat in flattenedMarketBooks.Take(5))
            {
               //Console.WriteLine($"  MarketId: {marketBookFlat.MarketId}, Status: {marketBookFlat.Status}, Total Matched: {marketBookFlat.TotalMatched}");
                if (marketBookFlat.Runners != null)
                {
                   Console.WriteLine($"    Runners in this MarketBook: {marketBookFlat.Runners.Count}");
                    // Print details of the first few runners to ensure data integrity
                    foreach (var runnerFlat in marketBookFlat.Runners.Take(5)) // Print first 5 runners per market book
                    {
                       Console.WriteLine($"      RunnerFlat Name: '{runnerFlat.RunnerName ?? "NULL"}' (SelId: {runnerFlat.SelectionId}), LPT: {runnerFlat.LastPriceTraded}");
                       Console.WriteLine($"        OwnerName: '{runnerFlat.OwnerName ?? "NULL"}'");
                       Console.WriteLine($"        Form: '{runnerFlat.Form ?? "NULL"}'");
                       Console.WriteLine($"        JockeyClaim: '{runnerFlat.JockeyClaim ?? "NULL"}'");
                       Console.WriteLine($"        OfficialRating: '{runnerFlat.OfficialRating ?? "NULL"}'");
                        // Add any other critical fields you're checking for "nulls" in the DB
                    }
                }
            }
           //Console.WriteLine($"--- Total Runners to attempt inserting across all market books: {totalRunnersToInsert} ---");
           //Console.WriteLine("ProcessHorseMarketBooksAsync: Calling InsertHorseMarketBooksIntoDatabase...");

            await _marketBookDb.InsertHorseMarketBooksIntoDatabase(flattenedMarketBooks);

           //Console.WriteLine("ProcessHorseMarketBooksAsync: InsertHorseMarketBooksIntoDatabase call completed.");
        }
        else
        {
           //Console.WriteLine("ProcessHorseMarketBooksAsync: No flattened market books to insert into the database.");
        }

        // Step 4: Return flattened runners
        var allFlattenedRunners = flattenedMarketBooks.SelectMany(marketBook => marketBook.Runners).ToList();
       //Console.WriteLine($"ProcessHorseMarketBooksAsync: Returning {allFlattenedRunners.Count} total RunnerFlat objects.");
        return allFlattenedRunners;
    }
    catch (Exception ex)
    {
       //Console.WriteLine($"ProcessHorseMarketBooksAsync ERROR: {ex.Message}");
       //Console.WriteLine($"Stack Trace: {ex.StackTrace}");
        if (ex.InnerException != null)
        {
           //Console.WriteLine($"Inner Exception: {ex.InnerException.Message}");
           //Console.WriteLine($"Inner Exception Stack Trace: {ex.InnerException.StackTrace}");
        }
        return new List<RunnerFlat>();
    }
        }
    }
}