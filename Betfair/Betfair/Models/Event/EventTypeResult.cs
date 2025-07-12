using System.Text.Json.Serialization;

namespace Betfair.Models.Event;
public class EventTypeResult
{
    [JsonPropertyName("eventType")]
    public EventType EventType { get; set; }

    [JsonPropertyName("marketCount")]
    public int MarketCount { get; set; }
}