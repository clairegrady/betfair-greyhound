using System.Data.Common;
using System.Text.Json;
using Betfair.Models.Account;

namespace Betfair.Handlers;
public class DisplayHandler
{
    public void DisplayMarketBookRow(DbDataReader reader)
    {
        try
        {
            var eventName = reader.IsDBNull(reader.GetOrdinal("EventName")) ? "N/A" : reader.GetString(reader.GetOrdinal("EventName"));
            var marketId = reader.IsDBNull(reader.GetOrdinal("MarketId")) ? "N/A" : reader.GetString(reader.GetOrdinal("MarketId"));
            var marketName = reader.IsDBNull(reader.GetOrdinal("MarketName")) ? "N/A" : reader.GetString(reader.GetOrdinal("MarketName"));
            var totalMatched = reader.IsDBNull(reader.GetOrdinal("TotalMatched")) ? 0 : reader.GetDecimal(reader.GetOrdinal("TotalMatched"));
            var selectionId = reader.IsDBNull(reader.GetOrdinal("SelectionId")) ? 0 : reader.GetInt32(reader.GetOrdinal("SelectionId"));
            var status = reader.IsDBNull(reader.GetOrdinal("Status")) ? "N/A" : reader.GetString(reader.GetOrdinal("Status"));
            var lastPriceTraded = reader.IsDBNull(reader.GetOrdinal("LastPriceTraded")) ? "N/A" : reader.GetDecimal(reader.GetOrdinal("LastPriceTraded")).ToString();
            var availableToBackPrice = reader.IsDBNull(reader.GetOrdinal("BackPrice")) ? "N/A" : reader.GetDecimal(reader.GetOrdinal("BackPrice")).ToString();
            var availableToBackSize = reader.IsDBNull(reader.GetOrdinal("BackSize")) ? "N/A" : reader.GetDecimal(reader.GetOrdinal("BackSize")).ToString();
            var availableToLayPrice = reader.IsDBNull(reader.GetOrdinal("LayPrice")) ? "N/A" : reader.GetDecimal(reader.GetOrdinal("LayPrice")).ToString();
            var availableToLaySize = reader.IsDBNull(reader.GetOrdinal("LaySize")) ? "N/A" : reader.GetDecimal(reader.GetOrdinal("LaySize")).ToString();
            
            if (string.IsNullOrEmpty(eventName) && string.IsNullOrEmpty(marketId) && string.IsNullOrEmpty(marketName))
            {
                return;
            }
            
            
            int maxEventNameLength = eventName.Length > 20 ? eventName.Length : 20;
            string formatString = $"{{0,-{maxEventNameLength}}} | {{1,-15}} | {{2,-18}} | {{3,-12}} | {{4,-11}} | {{5,-7}} | {{6,-15}} | {{7,-19}} | {{8,-19}} | {{9,-19}} | {{10,-19}}";
    
            //Console.WriteLine(string.Format(formatString, eventName, marketId, marketName, totalMatched, selectionId, status, lastPriceTraded, availableToBackPrice, availableToBackSize, availableToLayPrice, availableToLaySize));
        }
        catch (Exception ex)
        {
            //Console.WriteLine($"Error displaying row: {ex.Message}");
        }
    }
    public void DisplayHeader()
    {
        //Console.WriteLine("EventName                          | MarketId       | MarketName        | TotalMatched | SelectionId | Status | LastPriceTraded | AvailableToBackPrice | AvailableToBackSize | AvailableToLayPrice |AvailableToLaySize");
    }
    public void DisplayFooter()
    {
        //Console.WriteLine(new string('*', 215));
    }
    
    public static void DisplayAccountData(string accountFundsJson)
    {
        try
        {
            var accountFundsResponse = JsonSerializer.Deserialize<AccountFundsResponse>(accountFundsJson);

            if (accountFundsResponse != null && accountFundsResponse.Result != null)
            {
                var availableToBetBalance = accountFundsResponse.Result.AvailableToBetBalance;
                var exposure = accountFundsResponse.Result.Exposure;
                var retainedCommission = accountFundsResponse.Result.RetainedCommission;
                var exposureLimit = accountFundsResponse.Result.ExposureLimit;
                var discountRate = accountFundsResponse.Result.DiscountRate;
                var pointsBalance = accountFundsResponse.Result.PointsBalance;
                var wallet = accountFundsResponse.Result.Wallet;

                //Console.WriteLine("--------------------------------------------------------------------------------------------------------------------------");
                //Console.WriteLine("| Available to Bet Balance | Exposure | Retained Commission | Exposure Limit | Discount Rate | Points Balance | Wallet |");
                //Console.WriteLine("--------------------------------------------------------------------------------------------------------------------------");

                //Console.WriteLine($"| {availableToBetBalance,24} | {exposure,8} | {retainedCommission,19} | {exposureLimit,13} | {discountRate,12} | {pointsBalance,14} | {wallet,-6} |");
                //Console.WriteLine("--------------------------------------------------------------------------------------------------------------------------");
            }
            else
            {
                //Console.WriteLine("Error: 'result' property is missing or invalid in the JSON response.");
            }
        }
        catch (Exception ex)
        {
            //Console.WriteLine($"Error displaying account data: {ex.Message}");
        }
    }
}

