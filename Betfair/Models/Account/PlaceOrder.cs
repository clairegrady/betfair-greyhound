namespace Betfair.Models.Account;

public class PlaceInstruction
{
    public string SelectionId { get; set; }
    public double Handicap { get; set; }
    public string Side { get; set; }
    public string OrderType { get; set; }
    public LimitOrder LimitOrder { get; set; }
    public MarketOnCloseOrder MarketOnCloseOrder { get; set; }
    public string PersistenceType { get; set; }
    public string TimeInForce { get; set; }
    public double MinFillSize { get; set; }
}

public class LimitOrder
{
    public double Size { get; set; }
    public double Price { get; set; }
    public string PersistenceType { get; set; }
}

public class MarketOnCloseOrder
{
    public double Liability { get; set; }
}

public class InstructionReport
{
    public string Status { get; set; }
    public PlaceInstruction Instruction { get; set; }
    public string BetId { get; set; }
    public string PlacedDate { get; set; }
}