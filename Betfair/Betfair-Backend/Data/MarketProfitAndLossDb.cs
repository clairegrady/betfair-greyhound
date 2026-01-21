using Npgsql;
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
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        foreach (var marketProfitAndLoss in marketProfitAndLossList)
        {
            //Console.WriteLine($"Processing Market: {marketProfitAndLoss.MarketId}");
            
            await InsertMarketProfitAndLoss(connection, marketProfitAndLoss);

            foreach (var bet in marketProfitAndLoss.ProfitAndLosses)
            {
                await InsertBetProfitAndLoss(connection, marketProfitAndLoss.MarketId, bet);
            }
        }
    }
    private async Task InsertMarketProfitAndLoss(NpgsqlConnection connection, MarketProfitAndLoss marketProfitAndLoss)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT INTO marketprofitandloss 
            (marketid, netprofit, grossprofit, commissionapplied)
            VALUES 
            (@marketid, @netprofit, @grossprofit, @commissionapplied)
            ON CONFLICT (marketid) DO UPDATE SET
                netprofit = EXCLUDED.netprofit,
                grossprofit = EXCLUDED.grossprofit,
                commissionapplied = EXCLUDED.commissionapplied";
        
        command.Parameters.AddWithValue("@marketid", marketProfitAndLoss.MarketId);
        command.Parameters.AddWithValue("@netprofit", marketProfitAndLoss.NetProfit ?? 0);
        command.Parameters.AddWithValue("@grossprofit", marketProfitAndLoss.GrossProfit ?? 0);
        command.Parameters.AddWithValue("@commissionapplied", marketProfitAndLoss.CommissionApplied ?? 0);
        await command.ExecuteNonQueryAsync();
    }
    private async Task InsertBetProfitAndLoss(NpgsqlConnection connection, string marketId, BetProfitAndLoss bet)
    {
        using var command = connection.CreateCommand();
        command.CommandText = @"
            INSERT INTO betprofitandloss 
            (selectionid, marketid, ifwin)
            VALUES 
            (@selectionid, @marketid, @ifwin)
            ON CONFLICT (selectionid, marketid) DO UPDATE SET
                ifwin = EXCLUDED.ifwin";
        
        command.Parameters.AddWithValue("@selectionid", bet.SelectionId);
        command.Parameters.AddWithValue("@marketid", marketId);
        command.Parameters.AddWithValue("@ifwin", bet.IfWin);
        await command.ExecuteNonQueryAsync();
    }
}
