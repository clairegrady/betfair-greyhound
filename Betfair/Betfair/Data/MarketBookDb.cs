using Microsoft.Data.Sqlite;
using Betfair.Models.Market;

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
    public MarketBookDb(string connectionString)
    {
        _connectionString = connectionString;
    }
    public async Task InsertMarketBooksIntoDatabase(List<MarketBook> marketBooks)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();
        Console.WriteLine(new string('*', 215));

        using var transaction = await connection.BeginTransactionAsync();

        await DeleteExistingData(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });

        await ResetAutoIncrementCounters(connection, new List<string> { "MarketBookBackPrices", "MarketBookLayPrices" });

        foreach (var marketBook in marketBooks)
        {
            var marketId = marketBook.MarketId;

            foreach (var runner in marketBook.Runners)
            {
                if (runner.Exchange != null)
                {
                    foreach (var back in runner.Exchange.AvailableToBack)
                    {
                        if (await IsDataExist(connection, "MarketBookBackPrices", marketId, runner.SelectionId, back.Price))
                        {
                            Console.WriteLine($"Skipping duplicate Back bet data for Runner {runner.SelectionId}: Price = {back.Price}");
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
                        priceCommand.Parameters.AddWithValue("$Price", back.Price ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$Size", back.Size ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);

                        await priceCommand.ExecuteNonQueryAsync();
                    }

                    foreach (var lay in runner.Exchange.AvailableToLay)
                    {
                        if (await IsDataExist(connection, "MarketBookLayPrices", marketId, runner.SelectionId, lay.Price))
                        {
                            Console.WriteLine($"Skipping duplicate Lay bet data for Runner {runner.SelectionId}: Price = {lay.Price}");
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
                        priceCommand.Parameters.AddWithValue("$Price", lay.Price ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$Size", lay.Size ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$Status", runner.Status ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$LastPriceTraded", runner.LastPriceTraded ?? (object)DBNull.Value);
                        priceCommand.Parameters.AddWithValue("$TotalMatched", runner.TotalMatched ?? (object)DBNull.Value);

                        await priceCommand.ExecuteNonQueryAsync();
                    }
                }
            }
        }
        await transaction.CommitAsync();
    }
    
    public async Task InsertGreyhoundMarketBooksIntoDatabase(List<MarketBook> marketBooks)
{
    using var connection = new SqliteConnection(_connectionString);
    await connection.OpenAsync();

    using var transaction = await connection.BeginTransactionAsync();

    foreach (var marketBook in marketBooks)
    {
        var marketId = marketBook.MarketId;

        // Ensure correct calling of the helper method
        var marketList = await GetMarketNameAndEventNameByMarketId(connection, marketId);
        Console.WriteLine($"Market Name: {marketList.MarketName}, Event Name: {marketList.EventName}");
        
        // Optional: Log the MarketName for debugging purposes
        Console.WriteLine($"Market Id: {marketId}   Market Name: {marketList.MarketName}");

        using var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT INTO GreyhoundMarketBook 
            (MarketId, MarketName, SelectionId, Status, PriceType, Price, Size) 
            VALUES 
            ($MarketId, $MarketName, $SelectionId, $Status, $PriceType, $Price, $Size)";

        foreach (var runner in marketBook.Runners)
        {
            var selectionId = runner.SelectionId;
            var status = runner.Status;
            Console.WriteLine($"Market Id: {marketId}    Runner Id: {selectionId}    Status: {status}");

            // Insert basic market and runner information
            command.Parameters.Clear();
            command.Parameters.AddWithValue("$MarketId", marketId);
            command.Parameters.AddWithValue("$MarketName", marketList.MarketName);  // Insert the Market Name
            command.Parameters.AddWithValue("$SelectionId", selectionId);
            command.Parameters.AddWithValue("$Status", status);

            if (runner.Exchange != null && runner.Exchange.AvailableToBack != null)
            {
                foreach (var back in runner.Exchange.AvailableToBack)
                {
                    Console.WriteLine($"Runners Back:  {back.Price}   {back.Size} {runner.Exchange.AvailableToBack.Count}");
                }

                foreach (var back in runner.Exchange.AvailableToBack)
                {
                    command.Parameters.Clear();
                    command.Parameters.AddWithValue("$MarketId", marketId);
                    command.Parameters.AddWithValue("$MarketName", marketList.MarketName);  // Insert the Market Name
                    command.Parameters.AddWithValue("$SelectionId", selectionId);
                    command.Parameters.AddWithValue("$Status", status);
                    command.Parameters.AddWithValue("$PriceType", "AvailableToBack");
                    command.Parameters.AddWithValue("$Price", back.Price ?? (object)DBNull.Value);
                    command.Parameters.AddWithValue("$Size", back.Size ?? (object)DBNull.Value);

                    await command.ExecuteNonQueryAsync();
                }
            }

            Console.WriteLine($"AvailableToBack Count: {runner.Exchange.AvailableToBack.Count}");

            if (runner.Exchange != null && runner.Exchange.AvailableToLay != null && runner.Exchange.AvailableToLay.Any())
            {
                foreach (var lay in runner.Exchange.AvailableToLay)
                {
                    Console.WriteLine($"Runners Lay:  {lay.Price}   {lay.Size} {runner.Exchange.AvailableToLay.Count}");
                }

                foreach (var lay in runner.Exchange.AvailableToLay)
                {
                    command.Parameters.Clear();

                    command.Parameters.AddWithValue("$MarketId", marketId);
                    command.Parameters.AddWithValue("$MarketName", marketList.MarketName);  // Insert the Market Name
                    command.Parameters.AddWithValue("$SelectionId", selectionId);
                    command.Parameters.AddWithValue("$Status", status);
                    command.Parameters.AddWithValue("$PriceType", "AvailableToLay");
                    command.Parameters.AddWithValue("$Price", lay.Price ?? (object)DBNull.Value);
                    command.Parameters.AddWithValue("$Size", lay.Size ?? (object)DBNull.Value);

                    await command.ExecuteNonQueryAsync();
                }
            }
            Console.WriteLine($"AvailableToLay Count: {runner.Exchange.AvailableToLay.Count}");
        }
    }

    await transaction.CommitAsync();
}

    private async Task<MarketInfo> GetMarketNameAndEventNameByMarketId(SqliteConnection connection, string marketId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
        SELECT MarketName, EventName 
        FROM MarketCatalogue
        WHERE MarketId = $MarketId";

        // Bind the MarketId parameter correctly
        command.Parameters.AddWithValue("$MarketId", marketId);

        // Execute the command and get the result
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

    private async Task DeleteExistingData(SqliteConnection connection, List<string> tableNames)
    {
        foreach (var table in tableNames)
        {
            using var deleteCommand = connection.CreateCommand();
            deleteCommand.CommandText = $"DELETE FROM {table}";
            await deleteCommand.ExecuteNonQueryAsync();
        }
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

