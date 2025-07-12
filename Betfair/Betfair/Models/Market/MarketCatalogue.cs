using System.Text.Json.Serialization;
using Betfair.Models.Event;

namespace Betfair.Models.Market;
public class MarketCatalogue
{
    [JsonPropertyName("marketId")]
    public string MarketId { get; set; }

    [JsonPropertyName("marketName")]
    public string MarketName { get; set; }

    [JsonPropertyName("totalMatched")]
    public decimal? TotalMatched { get; set; }

    [JsonPropertyName("eventType")]
    public EventType EventType { get; set; }

    [JsonPropertyName("competition")]
    public Competition.Competition Competition { get; set; }
    
    [JsonPropertyName("event")]
    public Event.Event Event { get; set; }
}
