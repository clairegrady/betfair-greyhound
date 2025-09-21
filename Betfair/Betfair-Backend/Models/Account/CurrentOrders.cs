using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Betfair.Models.Orders
{
    public class CurrentOrderSummaryReport
    {
        [JsonPropertyName("currentOrders")]
        public List<CurrentOrderSummary> CurrentOrders { get; set; }

        [JsonPropertyName("moreAvailable")]
        public bool MoreAvailable { get; set; }
    }

    public class CurrentOrderSummary
    {
        [JsonPropertyName("betId")]
        public string BetId { get; set; }

        [JsonPropertyName("marketId")]
        public string MarketId { get; set; }

        [JsonPropertyName("selectionId")]
        public long SelectionId { get; set; }

        [JsonPropertyName("handicap")]
        public double Handicap { get; set; }

        [JsonPropertyName("priceSize")]
        public PriceSize PriceSize { get; set; }

        [JsonPropertyName("bspLiability")]
        public double BspLiability { get; set; }

        [JsonPropertyName("side")]
        public string Side { get; set; }   // BACK or LAY

        [JsonPropertyName("status")]
        public string Status { get; set; } // EXECUTABLE, EXECUTION_COMPLETE, etc.

        [JsonPropertyName("persistenceType")]
        public string PersistenceType { get; set; }

        [JsonPropertyName("orderType")]
        public string OrderType { get; set; }

        [JsonPropertyName("placedDate")]
        public DateTime PlacedDate { get; set; }

        [JsonPropertyName("matchedDate")]
        public DateTime? MatchedDate { get; set; }

        [JsonPropertyName("averagePriceMatched")]
        public double? AveragePriceMatched { get; set; }

        [JsonPropertyName("sizeMatched")]
        public double SizeMatched { get; set; }

        [JsonPropertyName("sizeRemaining")]
        public double SizeRemaining { get; set; }

        [JsonPropertyName("sizeLapsed")]
        public double SizeLapsed { get; set; }

        [JsonPropertyName("sizeCancelled")]
        public double SizeCancelled { get; set; }

        [JsonPropertyName("sizeVoided")]
        public double SizeVoided { get; set; }
    }

    public class PriceSize
    {
        [JsonPropertyName("price")]
        public double Price { get; set; }

        [JsonPropertyName("size")]
        public double Size { get; set; }
    }
}
