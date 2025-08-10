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
    if (marketBooks == null || !marketBooks.Any())
    {
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
                skippedMarketBooks++;
                continue;
            }

            var existingMarket = await connection.ExecuteScalarAsync<int>(
                "SELECT COUNT(1) FROM HorseMarketBook WHERE MarketId = @MarketId",
                new { MarketId = marketId });

            if (existingMarket > 0)
            {
                skippedMarketBooks++;
                continue;
            }

            var marketInfo = await GetMarketNameAndEventNameByMarketId(connection, marketId);
            string marketName = marketInfo?.MarketName ?? "Unknown";

            foreach (var runner in marketBook.Runners)
            {
                if (runner.SelectionId == null)
                {
                    continue;
                }

                // Log the OwnerName for debugging purposes
                Console.WriteLine($"Inserting Runner: SelectionId={runner.SelectionId}, OwnerName={runner.OwnerName}");

                var paramValues = new Dictionary<string, object>
                {
                    ["MarketId"] = marketId,
                    ["MarketName"] = marketInfo?.MarketName ?? "Unknown",
                    ["EventName"] = marketInfo?.EventName ?? "Unknown",
                    ["SelectionId"] = runner.SelectionId,
                    ["RunnerName"] = runner.RunnerName ?? "Unknown",
                    ["Status"] = runner.Status,
                    ["SIRE_NAME"] = runner.SireName,
                    ["CLOTH_NUMBER_ALPHA"] = runner.ClothNumberAlpha,
                    ["OFFICIAL_RATING"] = ParseNullableDouble(runner.OfficialRating) ?? 0.0,
                    ["COLOURS_DESCRIPTION"] = runner.ColoursDescription,
                    ["COLOURS_FILENAME"] = runner.ColoursFilename,
                    ["FORECASTPRICE_DENOMINATOR"] = ParseNullableInt(runner.ForecastPriceDenominator) ?? 0,
                    ["DAMSIRE_NAME"] = runner.DamsireName,
                    ["WEIGHT_VALUE"] = ParseNullableDouble(runner.WeightValue) ?? 0.0,
                    ["SEX_TYPE"] = runner.SexType,
                    ["DAYS_SINCE_LAST_RUN"] = ParseNullableInt(runner.DaysSinceLastRun) ?? 0,
                    ["WEARING"] = runner.Wearing,
                    ["OWNER_NAME"] = runner.OwnerName,
                    ["DAM_YEAR_BORN"] = ParseNullableInt(runner.DamYearBorn) ?? 0,
                    ["SIRE_BRED"] = runner.SireBred,
                    ["JOCKEY_NAME"] = runner.JockeyName,
                    ["DAM_BRED"] = runner.DamBred,
                    ["ADJUSTED_RATING"] = ParseNullableDouble(runner.AdjustedRating) ?? 0.0,
                    ["CLOTH_NUMBER"] = runner.ClothNumber,
                    ["SIRE_YEAR_BORN"] = ParseNullableInt(runner.SireYearBorn) ?? 0,
                    ["TRAINER_NAME"] = runner.TrainerName,
                    ["COLOUR_TYPE"] = runner.ColourType,
                    ["AGE"] = ParseNullableInt(runner.Age) ?? 0,
                    ["DAMSIRE_BRED"] = runner.DamsireBred,
                    ["JOCKEY_CLAIM"] = ParseNullableDouble(runner.JockeyClaim) ?? 0.0,
                    ["FORM"] = runner.Form ?? "N/A",
                    ["FORECASTPRICE_NUMERATOR"] = ParseNullableInt(runner.ForecastPriceNumerator) ?? 0,
                    ["BRED"] = runner.Bred,
                    ["DAM_NAME"] = runner.DamName,
                    ["DAMSIRE_YEAR_BORN"] = ParseNullableInt(runner.DamsireYearBorn) ?? 0,
                    ["STALL_DRAW"] = ParseNullableInt(runner.StallDraw) ?? 0,
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
    }
    catch (Exception ex)
    {
        await transaction.RollbackAsync();
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

    public async Task DeleteFinishedRacesAsync()
    {
        // Method removed as per request to avoid deletion logic.
    }
}
