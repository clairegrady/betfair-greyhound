using System.Text.Json.Serialization;
using Betfair.Models.Converters;

namespace Betfair.Models.Runner;

public class StartingPrice
{
    [JsonPropertyName("nearPrice")]
    [JsonConverter(typeof(NullableDoubleConverter))]
    public double? NearPrice { get; set; }

    [JsonPropertyName("farPrice")]
    [JsonConverter(typeof(NullableDoubleConverter))]
    public double? FarPrice { get; set; }

    [JsonPropertyName("actualSP")]
    [JsonConverter(typeof(NullableDoubleConverter))]
    public double? ActualSP { get; set; }

    [JsonPropertyName("backStakeTaken")]
    public List<object> BackStakeTaken { get; set; }

    [JsonPropertyName("layLiabilityTaken")]
    public List<object> LayLiabilityTaken { get; set; }
}
