using System.Text.Json.Serialization;
using Betfair.Models.Market;

namespace Betfair.Models.Runner;

public class ApiRunner
{
    [JsonPropertyName("selectionId")]
    public long SelectionId { get; set; }

    [JsonPropertyName("handicap")]
    public double Handicap { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; }

    [JsonPropertyName("lastPriceTraded")]
    public double? LastPriceTraded { get; set; }

    [JsonPropertyName("totalMatched")]
    public double? TotalMatched { get; set; }

    [JsonPropertyName("ex")]
    public Exchange Exchange { get; set; }

    [JsonPropertyName("description")]
    public RunnerDescription Description { get; set; } // ← Includes metadata

    [JsonPropertyName("sp")]
    public StartingPrice Sp { get; set; }
}
