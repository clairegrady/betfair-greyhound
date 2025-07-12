using System.Text.Json.Serialization;

namespace Betfair.Models.Event;
public class EventListResult
{
    [JsonPropertyName("event")]
    public Event Event { get; set; }

    [JsonPropertyName("marketCount")]
    public int MarketCount { get; set; }
}