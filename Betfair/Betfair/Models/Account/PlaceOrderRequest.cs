using System.Collections.Generic;
using System.Text.Json.Serialization;
using System.ComponentModel.DataAnnotations;

namespace Betfair.Models.Account
{
    public class PlaceOrderRequest
    {
        [JsonPropertyName("marketId")]
        [Required]
        public string MarketId { get; set; }

        [JsonPropertyName("instructions")]
        public List<PlaceOrderInstruction> Instructions { get; set; }

        [JsonPropertyName("customerRef")]
        public string CustomerRef { get; set; }

        [JsonPropertyName("selectionId")]
        [Required]
        public long SelectionId { get; set; }

        [JsonPropertyName("stake")]
        [Required]
        [Range(0.01, double.MaxValue, ErrorMessage = "Stake must be greater than 0")]
        public decimal Stake { get; set; }

        // Additional properties for betting
        [JsonPropertyName("side")]
        public string Side { get; set; } = "B"; // B = Back, L = Lay

        [JsonPropertyName("orderType")]
        public string OrderType { get; set; } = "L"; // L = Limit

        [JsonPropertyName("price")]
        public decimal? Price { get; set; }

        [JsonPropertyName("persistenceType")]
        public string PersistenceType { get; set; } = "LAPSE";

        [JsonPropertyName("timeInForce")]
        public string TimeInForce { get; set; } = "FILL_OR_KILL";
    }
}