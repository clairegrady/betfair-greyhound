using Microsoft.Data.Sqlite;
using Betfair.Models.Data;

namespace Betfair.Data
{
    public class HistoricalDataDb
    {
        private readonly string _connectionString;

        public HistoricalDataDb(string connectionString)
        {
            _connectionString = connectionString;
        }

       public async Task InsertHistoricalDataPackagesAsync(List<HistoricalDataPackage> dataPackages)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            using var transaction = await connection.BeginTransactionAsync();
            
            await DeleteExistingDataAsync(new List<string> { "HistoricalDataTable" });

            await ResetAutoIncrementCountersAsync(new List<string> { "HistoricalDataTable" });

            foreach (var package in dataPackages)
            {
                if (await IsDataExistAsync(connection, "HistoricalDataTable", package.Id, package.Date))
                {
                    //Console.WriteLine($"Skipping duplicate data for ID: {package.Id}, Date: {package.Date}");
                    continue;
                }

                using var command = connection.CreateCommand();
                command.CommandText = @"
                    INSERT INTO HistoricalDataTable
                    (Id, Name, Date, MarketId, EventId, Price, Size, Status, MarketType, Country, FileType)
                    VALUES
                    ($Id, $Name, $Date, $MarketId, $EventId, $Price, $Size, $Status, $MarketType, $Country, $FileType)";

                command.Parameters.AddWithValue("$Id", package.Id);
                command.Parameters.AddWithValue("$Name", package.Name ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Date", package.Date);
                command.Parameters.AddWithValue("$MarketId", package.MarketId ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$EventId", package.EventId ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Price", package.Price ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Size", package.Size ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Status", package.Status ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$MarketType", package.MarketType ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Country", package.Country ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$FileType", package.FileType ?? (object)DBNull.Value);

                await command.ExecuteNonQueryAsync();
            }

            await transaction.CommitAsync();
        }


        public async Task<bool> IsDataExistAsync(SqliteConnection connection, string tableName, object id, object date)
        {
            using var command = connection.CreateCommand();
            command.CommandText = $@"
                SELECT COUNT(1) 
                FROM {tableName} 
                WHERE Id = $Id 
                AND Date = $Date";

            command.Parameters.AddWithValue("$Id", id);
            command.Parameters.AddWithValue("$Date", date);

            var count = await command.ExecuteScalarAsync();
            return (long)count > 0;
        }

        public async Task DeleteExistingDataAsync(List<string> tableNames)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            foreach (var table in tableNames)
            {
                using var deleteCommand = connection.CreateCommand();
                deleteCommand.CommandText = $"DELETE FROM {table}";
                await deleteCommand.ExecuteNonQueryAsync();
            }
        }

        public async Task ResetAutoIncrementCountersAsync(List<string> tableNames)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            foreach (var table in tableNames)
            {
                using var resetCommand = connection.CreateCommand();
                resetCommand.CommandText = $"DELETE FROM SQLITE_SEQUENCE WHERE NAME = '{table}'";
                await resetCommand.ExecuteNonQueryAsync();
            }
        }

        public async Task<IEnumerable<HistoricalDataPackage>> GetHistoricalDataPackagesAsync()
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            var dataPackages = new List<HistoricalDataPackage>();

            using var command = connection.CreateCommand();
            command.CommandText = "SELECT * FROM HistoricalDataTable";

            using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var dataPackage = new HistoricalDataPackage
                {
                    Id = reader.GetString(0),
                    Name = reader.GetString(1),
                    Date = reader.GetDateTime(2),
                    MarketId = reader.IsDBNull(3) ? null : reader.GetString(3),
                    EventId = reader.IsDBNull(4) ? null : reader.GetString(4),
                    Price = reader.IsDBNull(5) ? null : reader.GetDecimal(5),
                    Size = reader.IsDBNull(6) ? null : reader.GetDecimal(6),
                    Status = reader.IsDBNull(7) ? null : reader.GetString(7),
                    MarketType = reader.IsDBNull(8) ? null : reader.GetString(8),
                    Country = reader.IsDBNull(9) ? null : reader.GetString(9),
                    FileType = reader.IsDBNull(10) ? null : reader.GetString(10)
                };
                dataPackages.Add(dataPackage);
            }
            return dataPackages;
        }
    }
}
