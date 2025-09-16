using System.Text.Json;
using Microsoft.Data.Sqlite;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Dapper;

namespace Betfair.Data;

public class MarketInfo
{
    public string? MarketName { get; set; }
    public string? EventName { get; set; }

    public void Deconstruct(out string? marketName, out string? eventName)
    {
        marketName = MarketName;
        eventName = EventName;
    }
}

public class MarketBookDb
{
    private readonly string _connectionString;

    public MarketBookDb(string connectionString)
    {
        _connectionString = connectionString;
        try
        {
            VerifyHorseMarketBookSchema();
        }
        catch (Exception)
        {
            // Log or handle initialization errors if necessary
        }
    }

    private void VerifyHorseMarketBookSchema()
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        var cmd = connection.CreateCommand();
        cmd.CommandText = "PRAGMA table_info(HorseMarketBook);";

        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            string colName = reader.GetString(1);
            if (colName.Equals("DAM_YEAR_BORN", StringComparison.OrdinalIgnoreCase))
            {
                // Column exists, no further action needed
            }
        }
    }
    public async Task InsertHorseMarketBooksIntoDatabase(List<MarketBook<RunnerFlat>> marketBooks)
{
    //Console.WriteLine($"🐎 InsertHorseMarketBooksIntoDatabase called with {marketBooks?.Count ?? 0} market books");
    
    if (marketBooks == null || !marketBooks.Any())
    {
        //Console.WriteLine("❌ No market books provided - returning early");
        return;
    }

    using var connection = new SqliteConnection(_connectionString);
    await connection.OpenAsync();
    using var transaction = await connection.BeginTransactionAsync();

    int successfulRunnerInserts = 0;
    int skippedMarketBooks = 0;

    try
    {
        foreach (var marketBook in marketBooks)
        {
            string marketId = marketBook.MarketId;
            //Console.WriteLine($"📊 Processing market: {marketId}");

            if (string.IsNullOrEmpty(marketId))
            {
                //Console.WriteLine("⚠️ Skipping market with empty MarketId");
                skippedMarketBooks++;
                continue;
            }

            //Console.WriteLine($"🏇 Processing market: {marketId} with {marketBook.Runners?.Count ?? 0} runners");

            var marketInfo = await GetMarketNameAndEventNameByMarketId(connection, marketId);
            string marketName = marketInfo?.MarketName ?? "Unknown";

            foreach (var runner in marketBook.Runners)
            {
                if (runner.SelectionId == null)
                {
                    //Console.WriteLine("⚠️ Skipping runner with null SelectionId");
                    continue;
                }

                // Check if this specific horse already exists
                var existingHorse = await connection.ExecuteScalarAsync<int>(
                    "SELECT COUNT(1) FROM HorseMarketBook WHERE MarketId = @MarketId AND SelectionId = @SelectionId",
                    new { MarketId = marketId, SelectionId = runner.SelectionId });

                if (existingHorse > 0)
                {
                    // Delete this specific horse's old record
                    await DeleteExistingHorseRecord(connection, marketId, runner.SelectionId);
                    //Console.WriteLine($"🔄 Replacing existing data for horse {runner.SelectionId} in market {marketId}");
                }

                // Log the OwnerName for debugging purposes
               // Console.WriteLine($"✅ Inserting Runner: SelectionId={runner.SelectionId}, Name={runner.RunnerName}, OwnerName={runner.OwnerName}");

                var paramValues = new Dictionary<string, object?>
                {
                    ["MarketId"] = marketId,
                    ["MarketName"] = marketName,
                    ["EventName"] = marketInfo?.EventName ?? "Unknown",
                    ["SelectionId"] = runner.SelectionId,
                    ["RunnerName"] = runner.RunnerName,
                    ["Status"] = runner.Status,
                    ["SIRE_NAME"] = runner.SireName,
                    ["CLOTH_NUMBER_ALPHA"] = runner.ClothNumberAlpha,
                    ["OFFICIAL_RATING"] = ParseNullableDouble(runner.OfficialRating),
                    ["COLOURS_DESCRIPTION"] = runner.ColoursDescription,
                    ["COLOURS_FILENAME"] = runner.ColoursFilename,
                    ["FORECASTPRICE_DENOMINATOR"] = ParseNullableInt(runner.ForecastPriceDenominator),
                    ["DAMSIRE_NAME"] = runner.DamsireName,
                    ["WEIGHT_VALUE"] = ParseNullableDouble(runner.WeightValue),
                    ["SEX_TYPE"] = runner.SexType,
                    ["DAYS_SINCE_LAST_RUN"] = ParseNullableInt(runner.DaysSinceLastRun),
                    ["WEARING"] = runner.Wearing,
                    ["OWNER_NAME"] = runner.OwnerName,
                    ["DAM_YEAR_BORN"] = ParseNullableInt(runner.DamYearBorn),
                    ["SIRE_BRED"] = runner.SireBred,
                    ["JOCKEY_NAME"] = runner.JockeyName,
                    ["DAM_BRED"] = runner.DamBred,
                    ["ADJUSTED_RATING"] = ParseNullableDouble(runner.AdjustedRating),
                    ["CLOTH_NUMBER"] = runner.ClothNumber,
                    ["SIRE_YEAR_BORN"] = ParseNullableInt(runner.SireYearBorn),
                    ["TRAINER_NAME"] = runner.TrainerName,
                    ["COLOUR_TYPE"] = runner.ColourType,
                    ["AGE"] = ParseNullableInt(runner.Age),
                    ["DAMSIRE_BRED"] = runner.DamsireBred,
                    ["JOCKEY_CLAIM"] = ParseNullableDouble(runner.JockeyClaim),
                    ["FORM"] = runner.Form,
                    ["FORECASTPRICE_NUMERATOR"] = ParseNullableInt(runner.ForecastPriceNumerator),
                    ["BRED"] = runner.Bred,
                    ["DAM_NAME"] = runner.DamName,
                    ["DAMSIRE_YEAR_BORN"] = ParseNullableInt(runner.DamsireYearBorn),
                    ["STALL_DRAW"] = ParseNullableInt(runner.StallDraw),
                    ["WEIGHT_UNITS"] = runner.WeightUnits
                };

                using var command = connection.CreateCommand();
                command.CommandText = @"
                INSERT INTO HorseMarketBook (
                    MarketId, MarketName, EventName, SelectionId, RUNNER_NAME, Status,
                    SIRE_NAME, STALL_DRAW, DAMSIRE_NAME, FORM, WEIGHT_VALUE,
                    SEX_TYPE, DAYS_SINCE_LAST_RUN, WEARING, OWNER_NAME, DAM_YEAR_BORN,
                    SIRE_BRED, JOCKEY_NAME, DAM_BRED, CLOTH_NUMBER, SIRE_YEAR_BORN,
                    TRAINER_NAME, COLOUR_TYPE, AGE, DAMSIRE_BRED, JOCKEY_CLAIM,
                    FORECASTPRICE_NUMERATOR, BRED, DAM_NAME, DAMSIRE_YEAR_BORN, WEIGHT_UNITS,
                    CLOTH_NUMBER_ALPHA, OFFICIAL_RATING, COLOURS_DESCRIPTION, COLOURS_FILENAME,
                    FORECASTPRICE_DENOMINATOR
                ) VALUES (
                    $MarketId, $MarketName, $EventName, $SelectionId, $RunnerName, $Status,
                    $SIRE_NAME, $STALL_DRAW, $DAMSIRE_NAME, $FORM, $WEIGHT_VALUE,
                    $SEX_TYPE, $DAYS_SINCE_LAST_RUN, $WEARING, $OWNER_NAME, $DAM_YEAR_BORN,
                    $SIRE_BRED, $JOCKEY_NAME, $DAM_BRED, $CLOTH_NUMBER, $SIRE_YEAR_BORN,
                    $TRAINER_NAME, $COLOUR_TYPE, $AGE, $DAMSIRE_BRED, $JOCKEY_CLAIM,
                    $FORECASTPRICE_NUMERATOR, $BRED, $DAM_NAME, $DAMSIRE_YEAR_BORN, $WEIGHT_UNITS,
                    $CLOTH_NUMBER_ALPHA, $OFFICIAL_RATING, $COLOURS_DESCRIPTION, $COLOURS_FILENAME,
                    $FORECASTPRICE_DENOMINATOR
                )";

                foreach (var kvp in paramValues)
                {
                    command.Parameters.AddWithValue($"${kvp.Key}", kvp.Value ?? (object)DBNull.Value);
                }

                await command.ExecuteNonQueryAsync();
                successfulRunnerInserts++;
            }
        }

        await transaction.CommitAsync();
        //Console.WriteLine($"✅ Successfully processed {successfulRunnerInserts} runners across {marketBooks.Count} market books.");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"❌ Error inserting horse market books: {ex.Message}");
        Console.WriteLine($"Stack trace: {ex.StackTrace}");
        await transaction.RollbackAsync();
    }
}

    public async Task InsertMarketBooksIntoDatabase(List<MarketBook<ApiRunner>> marketBooks)
    {
        Console.WriteLine($"📊 InsertMarketBooksIntoDatabase called with {marketBooks?.Count ?? 0} market books");

        if (marketBooks == null || !marketBooks.Any())
        {
            Console.WriteLine("❌ No market books provided to InsertMarketBooksIntoDatabase - returning early");
            return;
        }

        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();
        Console.WriteLine($"🔗 Database connection opened for back/lay price insertion");

        using var transaction = await connection.BeginTransactionAsync();

        await DeleteExistingData(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });
        await ResetAutoIncrementCounters(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });

        int totalBackPrices = 0;
        int totalLayPrices = 0;
        int processedMarkets = 0;

        try
        {
            foreach (var marketBook in marketBooks)
            {
                string marketId = marketBook.MarketId;
                //Console.WriteLine($"💰 Processing market {marketId} with {marketBook.Runners?.Count ?? 0} runners for back/lay prices");
                processedMarkets++;

                foreach (var runner in marketBook.Runners)
                {
                    //Console.WriteLine($"🏃 Processing runner {runner.SelectionId} with exchange data: {runner.Exchange != null}");

                    if (runner.Exchange != null)
                    {
                        //Console.WriteLine($"📈 Runner {runner.SelectionId} has {runner.Exchange.AvailableToBack?.Count ?? 0} back prices and {runner.Exchange.AvailableToLay?.Count ?? 0} lay prices");

                        foreach (var back in runner.Exchange.AvailableToBack)
                        {
                            if (await IsDataExist(connection, "MarketBookBackPrices", marketId, runner.SelectionId, back.Price))
                            {
                                //Console.WriteLine($"⚠️ Skipping duplicate Back bet data for Runner {runner.SelectionId}: Price = {back.Price}");
                                continue;
                            }

                            using var priceCommand = connection.CreateCommand();
                            priceCommand.CommandText = @"
                                INSERT INTO MarketBookBackPrices
                                (MarketId, SelectionId, Price, Size, Status, LastPriceTraded, TotalMatched)
                                VALUES
                                ($MarketId, $SelectionId, $Price, $Size, $Status, $LastPriceTraded, $TotalMatched)";

                            priceCommand.Parameters.AddWithValue("$MarketId", marketId ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                            priceCommand.Parameters.AddWithValue("$Price", (double)back.Price);
                            priceCommand.Parameters.AddWithValue("$Size", (double)back.Size);
                            priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);

                            await priceCommand.ExecuteNonQueryAsync();
                            totalBackPrices++;
                            //Console.WriteLine($"✅ Inserted back price: Market={marketId}, Runner={runner.SelectionId}, Price={back.Price}, Size={back.Size}");
                        }

                        foreach (var lay in runner.Exchange.AvailableToLay)
                        {
                            if (await IsDataExist(connection, "MarketBookLayPrices", marketId, runner.SelectionId, lay.Price))
                            {
                                //Console.WriteLine($"⚠️ Skipping duplicate Lay bet data for Runner {runner.SelectionId}: Price = {lay.Price}");
                                continue;
                            }

                            using var priceCommand = connection.CreateCommand();
                            priceCommand.CommandText = @"
                                INSERT INTO MarketBookLayPrices
                                (MarketId, SelectionId, Price, Size, Status, LastPriceTraded, TotalMatched)
                                VALUES
                                ($MarketId, $SelectionId, $Price, $Size, $Status, $LastPriceTraded, $TotalMatched)";

                            priceCommand.Parameters.AddWithValue("$MarketId", marketId ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                            priceCommand.Parameters.AddWithValue("$Price", (double)lay.Price);
                            priceCommand.Parameters.AddWithValue("$Size", (double)lay.Size);
                            priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                            priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);

                            await priceCommand.ExecuteNonQueryAsync();
                            totalLayPrices++;
                            //Console.WriteLine($"✅ Inserted lay price: Market={marketId}, Runner={runner.SelectionId}, Price={lay.Price}, Size={lay.Size}");
                        }
                    }
                    else
                    {
                        //Console.WriteLine($"❌ Runner {runner.SelectionId} has no exchange data");
                    }
                }
            }
            await transaction.CommitAsync();
            //Console.WriteLine($"🎉 Market book back/lay prices inserted successfully!");
            //Console.WriteLine($"📊 Total processed: {processedMarkets} markets, {totalBackPrices} back prices, {totalLayPrices} lay prices");
        }
        catch (Exception ex)
        {
            await transaction.RollbackAsync();
            Console.WriteLine($"❌ Error inserting market book prices: {ex.Message}");
            Console.WriteLine($"📋 Stack trace: {ex.StackTrace}");
        }
    }


    public async Task InsertGreyhoundMarketBooksIntoDatabase(List<MarketBook<ApiRunner>> marketBooks)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();
        using var transaction = await connection.BeginTransactionAsync();

        try
        {
            foreach (var marketBook in marketBooks)
            {
                string marketId = marketBook.MarketId;
                var marketInfo = await GetMarketNameAndEventNameByMarketId(connection, marketId);

                foreach (var runner in marketBook.Runners)
                {
                    if (runner.Exchange?.AvailableToBack != null)
                    {
                        foreach (var back in runner.Exchange.AvailableToBack)
                        {
                            using var command = connection.CreateCommand();
                            command.CommandText = @"
                                INSERT INTO GreyhoundMarketBook
                                (MarketId, MarketName, SelectionId, Status, PriceType, Price, Size)
                                VALUES
                                ($MarketId, $MarketName, $SelectionId, $Status, $PriceType, $Price, $Size)";

                            command.Parameters.AddWithValue("$MarketId", marketId ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$MarketName", marketInfo?.MarketName ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                            command.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$PriceType", "AvailableToBack");
                            command.Parameters.AddWithValue("$Price", (double)back.Price);
                            command.Parameters.AddWithValue("$Size", (double)back.Size);

                            await command.ExecuteNonQueryAsync();
                        }
                    }

                    if (runner.Exchange?.AvailableToLay != null)
                    {
                        foreach (var lay in runner.Exchange.AvailableToLay)
                        {
                            using var command = connection.CreateCommand();
                            command.CommandText = @"
                                INSERT INTO GreyhoundMarketBook
                                (MarketId, MarketName, SelectionId, Status, PriceType, Price, Size)
                                VALUES
                                ($MarketId, $MarketName, $SelectionId, $Status, $PriceType, $Price, $Size)";

                            command.Parameters.AddWithValue("$MarketId", marketId ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$MarketName", marketInfo?.MarketName ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$SelectionId", runner.SelectionId);
                            command.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                            command.Parameters.AddWithValue("$PriceType", "AvailableToLay");
                            command.Parameters.AddWithValue("$Price", (double)lay.Price);
                            command.Parameters.AddWithValue("$Size", (double)lay.Size);

                            await command.ExecuteNonQueryAsync();
                        }
                    }
                }
            }
            await transaction.CommitAsync();
            //Console.WriteLine("Greyhound market books inserted successfully.");
        }
        catch (Exception ex)
        {
            await transaction.RollbackAsync();
            //Console.WriteLine($"Error inserting greyhound market books: {ex.Message}");
            //Console.WriteLine(ex.ToString());
        }
    }

    public async Task<List<HorseMarketBook>> GetHorseMarketBooksAsync()
{
    using var connection = new SqliteConnection(_connectionString);
    await connection.OpenAsync();

    var query = @"SELECT MarketId, MarketName, EventName, SelectionId, RUNNER_NAME as RunnerName, Status, SIRE_NAME as SireName, DAMSIRE_NAME as DamsireName, TRAINER_NAME as TrainerName, AGE, WEIGHT_VALUE as WeightValue, COLOUR_TYPE as ColourType, FORM FROM HorseMarketBook";
    var result = await connection.QueryAsync<HorseMarketBook>(query);

    return result.ToList();
}

    private async Task<MarketInfo> GetMarketNameAndEventNameByMarketId(SqliteConnection connection, string marketId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
        SELECT MarketName, EventName
        FROM EventMarkets
        WHERE MarketId = $MarketId
        LIMIT 1";
        command.Parameters.AddWithValue("$MarketId", marketId);

        using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new MarketInfo
            {
                MarketName = reader.GetString(0),
                EventName = reader.GetString(1)
            };
        }

        Console.WriteLine($"No matching MarketId found in EventMarkets for MarketId: {marketId}");
        return new MarketInfo { MarketName = "Unknown", EventName = "Unknown" };
    }

    private static int? ParseNullableInt(string input) =>
        int.TryParse(input, out var result) ? result : null;

    private static double? ParseNullableDouble(string input) =>
        double.TryParse(input, out var result) ? result : null;

    private async Task DeleteExistingData(SqliteConnection connection, List<string> tableNames)
    {
        // Method removed as per request to avoid deletion logic.
    }

    private async Task<bool> IsDataExist(SqliteConnection connection, string tableName, object marketId, object selectionId, object price)
    {
        using var command = connection.CreateCommand();
        command.CommandText = $@"
        SELECT COUNT(1)
        FROM {tableName}
        WHERE MarketId = $MarketId
        AND SelectionId = $SelectionId
        AND Price = $Price";

        command.Parameters.AddWithValue("$MarketId", marketId);
        command.Parameters.AddWithValue("$SelectionId", selectionId);
        command.Parameters.AddWithValue("$Price", price ?? (object)DBNull.Value);

        //Console.WriteLine($"Checking if data exists in table {tableName} for MarketId: {marketId}, SelectionId: {selectionId}, Price: {price}");
        var count = await command.ExecuteScalarAsync();
        //Console.WriteLine($"Data exists: {(long)count > 0}");
        return (long)count > 0;
    }

    private async Task ResetAutoIncrementCounters(SqliteConnection connection, List<string> tableNames)
    {
        foreach (var table in tableNames)
        {
            using var resetCommand = connection.CreateCommand();
            resetCommand.CommandText = $"DELETE FROM SQLITE_SEQUENCE WHERE NAME = '{table}'";
            await resetCommand.ExecuteNonQueryAsync();
        }
    }

    private async Task DeleteExistingHorseRecord(SqliteConnection connection, string marketId, long selectionId)
    {
        using var deleteCommand = connection.CreateCommand();
        deleteCommand.CommandText = "DELETE FROM HorseMarketBook WHERE MarketId = @MarketId AND SelectionId = @SelectionId";
        deleteCommand.Parameters.AddWithValue("@MarketId", marketId);
        deleteCommand.Parameters.AddWithValue("@SelectionId", selectionId);
        await deleteCommand.ExecuteNonQueryAsync();
    }

    public async Task DeleteFinishedRacesAsync()
    {
        // Method removed as per request to avoid deletion logic.
    }

    public async Task<object> GetHorseBackAndLayOddsAsync(long selectionId)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        // First, get horse details from HorseMarketBook
        var horseQuery = @"
            SELECT MarketId, MarketName, EventName, RUNNER_NAME 
            FROM HorseMarketBook 
            WHERE SelectionId = @SelectionId 
            LIMIT 1";

        var horseInfo = await connection.QueryFirstOrDefaultAsync(horseQuery, new { SelectionId = selectionId });

        if (horseInfo == null)
        {
            return new { Error = $"Horse with SelectionId {selectionId} not found" };
        }

        // Get back odds from MarketBookBackPrices table
        var backOddsQuery = @"
            SELECT Price, Size, MarketId
            FROM MarketBookBackPrices 
            WHERE SelectionId = @SelectionId 
            ORDER BY Price DESC";

        var backOdds = await connection.QueryAsync(backOddsQuery, new { SelectionId = selectionId });

        // Get lay odds from MarketBookLayPrices table
        var layOddsQuery = @"
            SELECT Price, Size, MarketId
            FROM MarketBookLayPrices 
            WHERE SelectionId = @SelectionId 
            ORDER BY Price ASC";

        var layOdds = await connection.QueryAsync(layOddsQuery, new { SelectionId = selectionId });

        return new
        {
            Horse = new
            {
                SelectionId = selectionId,
                Name = horseInfo.RUNNER_NAME,
                MarketId = horseInfo.MarketId,
                MarketName = horseInfo.MarketName,
                EventName = horseInfo.EventName
            },
            BackOdds = backOdds.Select(b => new { Price = b.Price, Size = b.Size, MarketId = b.MarketId }),
            LayOdds = layOdds.Select(l => new { Price = l.Price, Size = l.Size, MarketId = l.MarketId })
        };
    }
}
