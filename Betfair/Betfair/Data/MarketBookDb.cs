using System.Text.Json;
using Microsoft.Data.Sqlite;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Dapper;

namespace Betfair.Data;

public class MarketInfo
{
    public string MarketName { get; set; }
    public string EventName { get; set; }

    public void Deconstruct(out string marketName, out string eventName)
    {
        marketName = MarketName;
        eventName = EventName;
    }
}

public class MarketBookDb
{
    private readonly string _connectionString;
    //
    // public MarketBookDb(string connectionString)
    // {
    //     _connectionString = connectionString;
    //     CreateHorseMarketBookTable();
    //     VerifyHorseMarketBookSchema();
    // }
    //
    public MarketBookDb(string connectionString)
    {
        _connectionString = connectionString;
        // --- ADD THESE LINES FOR DEBUGGING ---
        //Console.WriteLine($"DEBUG: MarketBookDb constructor called. Connection String: '{_connectionString}'");
        try
        {
            VerifyHorseMarketBookSchema();
        }
        catch (Exception ex)
        {
            //Console.WriteLine($"CRITICAL ERROR during MarketBookDb initialization: {ex.Message}");
            //Console.WriteLine(ex.ToString()); // This will print the full stack trace
            // Optionally re-throw if you want the app to crash if the DB isn't initialized
            // throw;
        }
        // --- END ADDED LINES ---
    }

    private void VerifyHorseMarketBookSchema()
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        var cmd = connection.CreateCommand();
        cmd.CommandText = "PRAGMA table_info(HorseMarketBook);"; // This SQLite pragma gives table info

        //Console.WriteLine("--- Verifying HorseMarketBook Schema ---");
        using var reader = cmd.ExecuteReader();
        bool foundDamYearBorn = false;
        while (reader.Read())
        {
            string colName = reader.GetString(1); // Column name is at index 1
            string colType = reader.GetString(2); // Column type is at index 2
            int notNull = reader.GetInt32(3);     // Not null status is at index 3 (1 for NOT NULL, 0 for NULLABLE)
            //Console.WriteLine($"Column: {colName}, Type: {colType}, Not Null: {(notNull == 1 ? "Yes" : "No")}");
            if (colName.Equals("DAM_YEAR_BORN", StringComparison.OrdinalIgnoreCase))
            {
                foundDamYearBorn = true;
            }
        }
        if (foundDamYearBorn)
        {
            //Console.WriteLine("SUCCESS: 'DAM_YEAR_BORN' column was found in the schema.");
        }
        else
        {
            //Console.WriteLine("ERROR: 'DAM_YEAR_BORN' column was NOT found in the schema. The table was not created or updated correctly.");
        }
        //Console.WriteLine("--------------------------------------");
    }
  public async Task InsertHorseMarketBooksIntoDatabase(List<MarketBook<RunnerFlat>> marketBooks)
{
    if (marketBooks == null || !marketBooks.Any())
    {
        //Console.WriteLine("No horse market books provided for insertion.");
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

            if (string.IsNullOrEmpty(marketId))
            {
                // Console.WriteLine($"WARNING: Skipping market book because MarketId is null or empty. MarketBook details: {JsonSerializer.Serialize(marketBook)}");
                skippedMarketBooks++;
                continue;
            }

            // Check if the market already exists to avoid duplicates
            var existingMarket = await connection.ExecuteScalarAsync<int>(
                "SELECT COUNT(1) FROM HorseMarketBook WHERE MarketId = @MarketId",
                new { MarketId = marketId });

            if (existingMarket > 0)
            {
                // Skip if the market already exists
                skippedMarketBooks++;
                continue;
            }

            var marketInfo = await GetMarketNameAndEventNameByMarketId(connection, marketId);
            string marketName = marketInfo?.MarketName ?? "Unknown";

            foreach (var runner in marketBook.Runners)
            {
                if (runner.SelectionId == null)
                {
                    //Console.WriteLine($"WARNING: Skipping runner with missing SelectionId. MarketId: {marketId}");
                    continue;
                }

                var paramValues = new Dictionary<string, object>
                {
                    ["MarketId"] = marketId,
                    ["MarketName"] = marketInfo?.MarketName ?? "Unknown",
                    ["EventName"] = marketInfo?.EventName ?? "Unknown",
                    ["SelectionId"] = runner.SelectionId,
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
                    ["FORM"] = runner.Form ?? "N/A",  // Handle empty form gracefully
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
                    MarketId, MarketName, EventName, SelectionId, Status,
                    SIRE_NAME, CLOTH_NUMBER_ALPHA, OFFICIAL_RATING, COLOURS_DESCRIPTION,
                    COLOURS_FILENAME, FORECASTPRICE_DENOMINATOR, DAMSIRE_NAME, WEIGHT_VALUE,
                    SEX_TYPE, DAYS_SINCE_LAST_RUN, WEARING, OWNER_NAME, DAM_YEAR_BORN,
                    SIRE_BRED, JOCKEY_NAME, DAM_BRED, ADJUSTED_RATING, CLOTH_NUMBER,
                    SIRE_YEAR_BORN, TRAINER_NAME, COLOUR_TYPE, AGE, DAMSIRE_BRED,
                    JOCKEY_CLAIM, FORM, FORECASTPRICE_NUMERATOR, BRED, DAM_NAME,
                    DAMSIRE_YEAR_BORN, STALL_DRAW, WEIGHT_UNITS
                ) VALUES (
                    $MarketId, $MarketName, $EventName, $SelectionId, $Status,
                    $SIRE_NAME, $CLOTH_NUMBER_ALPHA, $OFFICIAL_RATING, $COLOURS_DESCRIPTION,
                    $COLOURS_FILENAME, $FORECASTPRICE_DENOMINATOR, $DAMSIRE_NAME, $WEIGHT_VALUE,
                    $SEX_TYPE, $DAYS_SINCE_LAST_RUN, $WEARING, $OWNER_NAME, $DAM_YEAR_BORN,
                    $SIRE_BRED, $JOCKEY_NAME, $DAM_BRED, $ADJUSTED_RATING, $CLOTH_NUMBER,
                    $SIRE_YEAR_BORN, $TRAINER_NAME, $COLOUR_TYPE, $AGE, $DAMSIRE_BRED,
                    $JOCKEY_CLAIM, $FORM, $FORECASTPRICE_NUMERATOR, $BRED, $DAM_NAME,
                    $DAMSIRE_YEAR_BORN, $STALL_DRAW, $WEIGHT_UNITS
                )";


                foreach (var kvp in paramValues)
                {
                    command.Parameters.AddWithValue($"${kvp.Key}", kvp.Value ?? (object)DBNull.Value);
                }
                Console.WriteLine($"##########Inserting MarketId: {marketId}, MarketName: {paramValues["MarketName"]}, EventName: {paramValues["EventName"]}");

                await command.ExecuteNonQueryAsync();
                successfulRunnerInserts++;
            }
        }

        await transaction.CommitAsync();
        // Console.WriteLine($"Successfully inserted {successfulRunnerInserts} horse market runners. Skipped {skippedMarketBooks} market books due to null/empty MarketId.");
    }
    catch (Exception ex)
    {
        await transaction.RollbackAsync();
        // Console.WriteLine($"Error inserting horse market books: {ex.Message}");
        // Console.WriteLine(ex);
    }
}



    public async Task InsertMarketBooksIntoDatabase(List<MarketBook<ApiRunner>> marketBooks)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();
        //Console.WriteLine(new string('*', 215));

        using var transaction = await connection.BeginTransactionAsync();

        await DeleteExistingData(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });
        await ResetAutoIncrementCounters(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });

        try
        {
            foreach (var marketBook in marketBooks)
            {
                string marketId = marketBook.MarketId;

                foreach (var runner in marketBook.Runners)
                {
                    if (runner.Exchange != null)
                    {
                        foreach (var back in runner.Exchange.AvailableToBack)
                        {
                            if (await IsDataExist(connection, "MarketBookBackPrices", marketId, runner.SelectionId, back.Price))
                            {
                                //Console.WriteLine($"Skipping duplicate Back bet data for Runner {runner.SelectionId}: Price = {back.Price}");
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
                        }

                        foreach (var lay in runner.Exchange.AvailableToLay)
                        {
                            if (await IsDataExist(connection, "MarketBookLayPrices", marketId, runner.SelectionId, lay.Price))
                            {
                                //Console.WriteLine($"Skipping duplicate Lay bet data for Runner {runner.SelectionId}: Price = {lay.Price}");
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
                        }
                    }
                }
            }
            await transaction.CommitAsync();
            //Console.WriteLine("Market book back/lay prices inserted successfully.");
        }
        catch (Exception ex)
        {
            await transaction.RollbackAsync();
            //Console.WriteLine($"Error inserting market book prices: {ex.Message}");
            //Console.WriteLine(ex.ToString());
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

    private async Task<MarketInfo> GetMarketNameAndEventNameByMarketId(SqliteConnection connection, string marketId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT mc.MarketName, el.Name
            FROM MarketCatalogue mc
            JOIN EventList el ON mc.EventId = el.Id
            WHERE mc.MarketId = $MarketId";
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

        return null;
    }

    private static int? ParseNullableInt(string input) =>
        int.TryParse(input, out var result) ? result : null;

    private static double? ParseNullableDouble(string input) =>
        double.TryParse(input, out var result) ? result : null;

    private async Task DeleteExistingData(SqliteConnection connection, List<string> tableNames)
    {
        foreach (var table in tableNames)
        {
            using var deleteCommand = connection.CreateCommand();
            deleteCommand.CommandText = $"DELETE FROM {table}";
            await deleteCommand.ExecuteNonQueryAsync();
        }
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

        var count = await command.ExecuteScalarAsync();
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
}