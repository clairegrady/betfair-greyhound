using System.Text.Json.Serialization;

namespace Betfair.Models.Data;
public class HistoricalDataPackage
{
    [JsonPropertyName("id")]  
    public string Id { get; set; }   

    [JsonPropertyName("name")] 
    public string Name { get; set; }

    [JsonPropertyName("date")] 
    public DateTime Date { get; set; }

    [JsonPropertyName("marketId")]
    public string MarketId { get; set; }

    [JsonPropertyName("eventId")]
    public string EventId { get; set; }

    [JsonPropertyName("price")]
    public decimal? Price { get; set; }

    [JsonPropertyName("size")]
    public decimal? Size { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; }

    [JsonPropertyName("marketType")]
    public string MarketType { get; set; }

    [JsonPropertyName("country")]
    public string Country { get; set; }

    [JsonPropertyName("fileType")]
    public string FileType { get; set; }

    [JsonPropertyName("fileSize")]
    public long FileSize { get; set; }
}
