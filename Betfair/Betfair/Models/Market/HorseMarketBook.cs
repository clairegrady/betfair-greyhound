using Newtonsoft.Json;

namespace Betfair.Models.Market;

public class HorseMarketBook
{
    [JsonProperty("marketId")]
    public string MarketId { get; set; }

    [JsonProperty("marketName")]
    public string MarketName { get; set; }

    [JsonProperty("eventName")]
    public string EventName { get; set; }

    [JsonProperty("selectionId")]
    public string SelectionId { get; set; }

    [JsonProperty("runnerName")]
    public string RunnerName { get; set; }

    [JsonProperty("status")]
    public string Status { get; set; }

    [JsonProperty("sireName")]
    public string SireName { get; set; }

    [JsonProperty("damsireName")]
    public string DamsireName { get; set; }

    [JsonProperty("trainerName")]
    public string TrainerName { get; set; }

    [JsonProperty("age")]
    public int? Age { get; set; }

    [JsonProperty("weightValue")]
    public double? WeightValue { get; set; }

    [JsonProperty("colourType")]
    public string ColourType { get; set; }

    [JsonProperty("form")]
    public string Form { get; set; }
}
