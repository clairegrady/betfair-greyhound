using System.Text.Json.Serialization;

namespace Betfair.Models.Competition;
public class Competition
{
    [JsonPropertyName("id")]
    public string Id { get; set; }

    [JsonPropertyName("name")]
    public string Name { get; set; }
}
