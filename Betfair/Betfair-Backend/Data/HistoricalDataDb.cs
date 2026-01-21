using Npgsql;
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
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            using var transaction = await connection.BeginTransactionAsync();
            
            await DeleteExistingDataAsync(new List<string> { "historicaldatatable" });

            await ResetAutoIncrementCountersAsync(new List<string> { "historicaldatatable" });

            foreach (var package in dataPackages)
            {
                if (await IsDataExistAsync(connection, "historicaldatatable", package.Id, package.Date))
                {
                    //Console.WriteLine($"Skipping duplicate data for ID: {package.Id}, Date: {package.Date}");
                    continue;
                }

                using var command = connection.CreateCommand();
                command.CommandText = @"
                    INSERT INTO historicaldatatable
                    (id, name, date, marketid, eventid, price, size, status, markettype, country, filetype)
                    VALUES
                    (@id, @name, @date, @marketid, @eventid, @price, @size, @status, @markettype, @country, @filetype)";

                command.Parameters.AddWithValue("@id", package.Id);
                command.Parameters.AddWithValue("@name", (object?)package.Name ?? DBNull.Value);
                command.Parameters.AddWithValue("@date", package.Date);
                command.Parameters.AddWithValue("@marketid", (object?)package.MarketId ?? DBNull.Value);
                command.Parameters.AddWithValue("@eventid", (object?)package.EventId ?? DBNull.Value);
                command.Parameters.AddWithValue("@price", (object?)package.Price ?? DBNull.Value);
                command.Parameters.AddWithValue("@size", (object?)package.Size ?? DBNull.Value);
                command.Parameters.AddWithValue("@status", (object?)package.Status ?? DBNull.Value);
                command.Parameters.AddWithValue("@markettype", (object?)package.MarketType ?? DBNull.Value);
                command.Parameters.AddWithValue("@country", (object?)package.Country ?? DBNull.Value);
                command.Parameters.AddWithValue("@filetype", (object?)package.FileType ?? DBNull.Value);

                await command.ExecuteNonQueryAsync();
            }

            await transaction.CommitAsync();
        }


        public async Task<bool> IsDataExistAsync(NpgsqlConnection connection, string tableName, object id, object date)
        {
            using var command = connection.CreateCommand();
            command.CommandText = $@"
                SELECT COUNT(1) 
                FROM {tableName} 
                WHERE id = @id 
                AND date = @date";

            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@date", date);

            var count = await command.ExecuteScalarAsync();
            return Convert.ToInt64(count) > 0;
        }

        public async Task DeleteExistingDataAsync(List<string> tableNames)
        {
            using var connection = new NpgsqlConnection(_connectionString);
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
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            foreach (var table in tableNames)
            {
                using var resetCommand = connection.CreateCommand();
                // PostgreSQL uses sequences for auto-increment, restart at 1
                resetCommand.CommandText = $"ALTER SEQUENCE {table}_id_seq RESTART WITH 1";
                try
                {
                    await resetCommand.ExecuteNonQueryAsync();
                }
                catch
                {
                    // Sequence may not exist, that's ok
                }
            }
        }

        public async Task<IEnumerable<HistoricalDataPackage>> GetHistoricalDataPackagesAsync()
        {
            using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();

            var dataPackages = new List<HistoricalDataPackage>();

            using var command = connection.CreateCommand();
            command.CommandText = "SELECT * FROM historicaldatatable";

            using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var dataPackage = new HistoricalDataPackage
                {
                    Id = reader.GetString(0),
                    Name = reader.IsDBNull(1) ? null : reader.GetString(1),
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
