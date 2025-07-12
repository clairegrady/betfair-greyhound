using Microsoft.Data.Sqlite;
using Betfair.Models.Market;

namespace Betfair.Data;
public class MarketProfitAndLossDb
{
    private readonly string _connectionString;
    public MarketProfitAndLossDb(string connectionString)
    {
        _connectionString = connectionString;
    }
    public async Task InsertMarketProfitAndLossIntoDatabase(List<MarketProfitAndLoss> marketProfitAndLossList)
    {
        using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var marketProfitAndLoss in marketProfitAndLossList)
        {
            Console.WriteLine($"Processing Market: {marketProfitAndLoss.MarketId}");
            
            await InsertMarketProfitAndLoss(connection, marketProfitAndLoss);

            foreach (var bet in marketProfitAndLoss.ProfitAndLosses)
            {
                await InsertBetProfitAndLoss(connection, marketProfitAndLoss.MarketId, bet);
            }
        }
    }
    private async Task InsertMarketProfitAndLoss(SqliteConnection connection, MarketProfitAndLoss marketProfitAndLoss)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT OR REPLACE INTO MarketProfitAndLoss 
            (MarketId, NetProfit, GrossProfit, CommissionApplied)
            VALUES 
            ($MarketId, $NetProfit, $GrossProfit, $CommissionApplied)";
        
        command.Parameters.AddWithValue("$MarketId", marketProfitAndLoss.MarketId);
        command.Parameters.AddWithValue("$NetProfit", marketProfitAndLoss.NetProfit ?? 0); // Use 0 if NetProfit is null
        command.Parameters.AddWithValue("$GrossProfit", marketProfitAndLoss.GrossProfit ?? 0); // Use 0 if GrossProfit is null
        command.Parameters.AddWithValue("$CommissionApplied", marketProfitAndLoss.CommissionApplied ?? 0); // Use 0 if CommissionApplied is null
        await command.ExecuteNonQueryAsync();
    }
    private async Task InsertBetProfitAndLoss(SqliteConnection connection, string marketId, BetProfitAndLoss bet)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT OR REPLACE INTO BetProfitAndLoss 
            (SelectionId, MarketId, IfWin)
            VALUES 
            ($SelectionId, $MarketId, $IfWin)";
        
        command.Parameters.AddWithValue("$SelectionId", bet.SelectionId);
        command.Parameters.AddWithValue("$MarketId", marketId);
        command.Parameters.AddWithValue("$IfWin", bet.IfWin);
        await command.ExecuteNonQueryAsync();
    }
}

