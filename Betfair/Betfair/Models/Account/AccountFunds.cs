using System.Text.Json.Serialization;

namespace Betfair.Models.Account;
public class AccountFunds
{
    [JsonPropertyName("availableToBetBalance")]
    public decimal AvailableToBetBalance { get; set; }

    [JsonPropertyName("exposure")]
    public decimal Exposure { get; set; }

    [JsonPropertyName("retainedCommission")]
    public decimal RetainedCommission { get; set; }

    [JsonPropertyName("exposureLimit")]
    public decimal ExposureLimit { get; set; }

    [JsonPropertyName("discountRate")]
    public decimal DiscountRate { get; set; }

    [JsonPropertyName("pointsBalance")]
    public int PointsBalance { get; set; }

    [JsonPropertyName("wallet")]
    public string Wallet { get; set; }
}

public class AccountFundsResponse
{
    [JsonPropertyName("result")]
    public AccountFunds Result { get; set; }  // Maps the 'result' property in the root object
}
