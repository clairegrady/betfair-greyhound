using System.Text.Json.Serialization;

namespace Betfair.Models.Account;

public class PlaceOrderInstruction
{
    [JsonPropertyName("selectionId")]
    public long SelectionId { get; set; }

    [JsonPropertyName("handicap")]
    public double Handicap { get; set; }

    [JsonPropertyName("side")]
    public string Side { get; set; }

    [JsonPropertyName("orderType")]
    public string OrderType { get; set; }

    [JsonPropertyName("limitOrder")]
    public LimitOrder? LimitOrder { get; set; }

    [JsonPropertyName("limitOnCloseOrder")]
    public LimitOnCloseOrder? LimitOnCloseOrder { get; set; }

    [JsonPropertyName("marketOnCloseOrder")]
    public MarketOnCloseOrder? MarketOnCloseOrder { get; set; }

    [JsonPropertyName("persistenceType")]
    public string? PersistenceType { get; set; }

    [JsonPropertyName("timeInForce")]
    public string? TimeInForce { get; set; }

    [JsonPropertyName("minFillSize")]
    public double MinFillSize { get; set; }
}

public class LimitOrder
{
    [JsonPropertyName("size")]
    public double Size { get; set; }

    [JsonPropertyName("price")]
    public double Price { get; set; }

    [JsonPropertyName("persistenceType")]
    public string PersistenceType { get; set; }
}

public class LimitOnCloseOrder
{
    [JsonPropertyName("price")]
    public double Price { get; set; }

    [JsonPropertyName("liability")]
    public double Liability { get; set; }
}

public class MarketOnCloseOrder
{
    [JsonPropertyName("liability")]
    public double Liability { get; set; }
}

public class InstructionReport
{
    [JsonPropertyName("status")]
    public string Status { get; set; }

    [JsonPropertyName("instruction")]
    public PlaceOrderInstruction Instruction { get; set; }

    [JsonPropertyName("betId")]
    public string BetId { get; set; }

    [JsonPropertyName("placedDate")]
    public string PlacedDate { get; set; }
}