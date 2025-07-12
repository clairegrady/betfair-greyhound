using System.Text.Json.Serialization;

namespace Betfair.Models.Event;
public class EventType
{
    [JsonPropertyName("id")]
    public string Id { get; set; }

    [JsonPropertyName("name")]
    public string Name { get; set; }
}
