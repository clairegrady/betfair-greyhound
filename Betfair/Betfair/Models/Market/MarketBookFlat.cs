using System.Text.Json.Serialization;
using Betfair.Models.Runner;

public class MarketBookFlat
{
    [JsonPropertyName("market_id")]
    public string MarketId { get; set; }

    [JsonPropertyName("is_market_data_delayed")]
    public bool? IsMarketDataDelayed { get; set; }

    [JsonPropertyName("status")]
    public string? Status { get; set; }

    [JsonPropertyName("bet_delay")]
    public int? BetDelay { get; set; }

    [JsonPropertyName("bsp_reconciled")]
    public bool? BspReconciled { get; set; }

    [JsonPropertyName("complete")]
    public bool? Complete { get; set; }

    [JsonPropertyName("inplay")]
    public bool? Inplay { get; set; }

    [JsonPropertyName("number_of_winners")]
    public int? NumberOfWinners { get; set; }

    [JsonPropertyName("number_of_runners")]
    public int? NumberOfRunners { get; set; }

    [JsonPropertyName("number_of_active_runners")]
    public int? NumberOfActiveRunners { get; set; }

    [JsonPropertyName("last_match_time")]
    public DateTime? LastMatchTime { get; set; }

    [JsonPropertyName("total_matched")]
    public double? TotalMatched { get; set; }

    [JsonPropertyName("total_available")]
    public double? TotalAvailable { get; set; }

    [JsonPropertyName("cross_matching")]
    public bool? CrossMatching { get; set; }

    [JsonPropertyName("runners_voidable")]
    public bool? RunnersVoidable { get; set; }

    [JsonPropertyName("version")]
    public long? Version { get; set; }

    [JsonPropertyName("runners")]
    public List<RunnerFlat>? Runners { get; set; }
}