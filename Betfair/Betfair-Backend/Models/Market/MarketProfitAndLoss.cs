using System.Text.Json.Serialization;

namespace Betfair.Models.Market;
public class MarketProfitAndLossApiResponse
{
    [JsonPropertyName("result")]
    public List<MarketProfitAndLoss> Result { get; set; }
}

public class MarketProfitAndLoss
{
    [JsonPropertyName("marketId")]
    public string MarketId { get; set; }

    [JsonPropertyName("profitAndLosses")]
    public List<BetProfitAndLoss> ProfitAndLosses { get; set; }
    public decimal? NetProfit { get; set; }
    public decimal? GrossProfit { get; set; }
    public decimal? CommissionApplied { get; set; }
}

public class BetProfitAndLoss
{
    [JsonPropertyName("selectionId")]
    public long SelectionId { get; set; }

    [JsonPropertyName("ifWin")]
    public decimal IfWin { get; set; }
}