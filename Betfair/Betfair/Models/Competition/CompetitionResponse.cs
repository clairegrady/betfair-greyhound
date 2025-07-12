using System.Text.Json.Serialization;

namespace Betfair.Models.Competition;

public class CompetitionResponse
{
    [JsonPropertyName("competition")]
    public Competition Competition { get; set; }

    [JsonPropertyName("marketCount")]
    public int MarketCount { get; set; }

    [JsonPropertyName("competitionRegion")]
    public string CompetitionRegion { get; set; }
}