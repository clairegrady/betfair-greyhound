namespace Betfair.Models.Account;

public class CancelInstruction
{
    public string betId { get; set; }
    public string size { get; set; }
}

public class UpdateInstruction
{
    public string betId { get; set; }
    public double size { get; set; }
    public double price { get; set; }
}

public class ReplaceInstruction
{
    public string betId { get; set; }  // The ID of the bet to replace
    public double price { get; set; }  // New price for the bet
    public double size { get; set; }   // New size for the bet
    public string side { get; set; }   // "BACK" or "LAY" (the side of the bet)
}
public class ReplaceOrdersRequest
{
    public string MarketId { get; set; }
    public List<ReplaceInstruction> Instructions { get; set; }
    public string CustomerRef { get; set; }
    public MarketVersion? MarketVersion { get; set; }  // OPTIONAL per Betfair docs
    public bool Async { get; set; } = false;
}

public class MarketVersion
{
    public string version { get; set; }
}