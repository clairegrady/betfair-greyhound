using System.Text.Json.Serialization;

namespace Betfair.Models.Event;
public class Event
{
    [JsonPropertyName("id")]
    public string Id { get; set; }

    [JsonPropertyName("name")]
    public string Name { get; set; }

    [JsonPropertyName("countryCode")]
    public string CountryCode { get; set; }

    [JsonPropertyName("timezone")]
    public string Timezone { get; set; }

    [JsonPropertyName("openDate")]
    public DateTime? OpenDate { get; set; }
}