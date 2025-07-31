using System.Text.Json.Serialization;
using Betfair.Models.Runner;

namespace Betfair.Models.Market
{
    public class MarketBook<TRunner>
    {
        [JsonPropertyName("marketId")]
        public string MarketId { get; set; }

        [JsonPropertyName("marketName")]
        public string MarketName { get; set; }

        [JsonPropertyName("eventName")]
        public string EventName { get; set; }

        [JsonPropertyName("isMarketDataDelayed")]
        public bool IsMarketDataDelayed { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; }

        [JsonPropertyName("betDelay")]
        public int BetDelay { get; set; }

        [JsonPropertyName("bspReconciled")]
        public bool BspReconciled { get; set; }

        [JsonPropertyName("complete")]
        public bool Complete { get; set; }

        [JsonPropertyName("inplay")]
        public bool Inplay { get; set; }

        [JsonPropertyName("numberOfWinners")]
        public int NumberOfWinners { get; set; }

        [JsonPropertyName("numberOfRunners")]
        public int NumberOfRunners { get; set; }

        [JsonPropertyName("numberOfActiveRunners")]
        public int NumberOfActiveRunners { get; set; }

        [JsonPropertyName("lastMatchTime")]
        public DateTime LastMatchTime { get; set; }

        [JsonPropertyName("totalMatched")]
        public double TotalMatched { get; set; }

        [JsonPropertyName("totalAvailable")]
        public double TotalAvailable { get; set; }

        [JsonPropertyName("crossMatching")]
        public bool CrossMatching { get; set; }

        [JsonPropertyName("runnersVoidable")]
        public bool RunnersVoidable { get; set; }

        [JsonPropertyName("version")]
        public long Version { get; set; }

        [JsonPropertyName("runners")]
        public List<TRunner> Runners { get; set; }
    }
    public class Exchange
    {
        [JsonPropertyName("availableToBack")]
        public List<PriceSize> AvailableToBack { get; set; }

        [JsonPropertyName("availableToLay")]
        public List<PriceSize> AvailableToLay { get; set; }

        [JsonPropertyName("tradedVolume")]
        public List<PriceSize> TradedVolume { get; set; }
    }

    public class PriceSize
    {
        [JsonPropertyName("price")]
        public decimal? Price { get; set; }

        [JsonPropertyName("size")]
        public decimal? Size { get; set; }
    }
}
