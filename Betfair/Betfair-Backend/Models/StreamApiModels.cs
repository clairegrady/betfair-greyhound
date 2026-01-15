using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

// Custom converter to handle "NaN" strings from Betfair API
public class NaNSafeDoubleConverter : JsonConverter<double?>
{
    public override double? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.String)
        {
            string stringValue = reader.GetString();
            if (stringValue == "NaN")
                return null;
            if (double.TryParse(stringValue, out double result))
                return result;
        }
        else if (reader.TokenType == JsonTokenType.Number)
        {
            return reader.GetDouble();
        }
        return null;
    }

    public override void Write(Utf8JsonWriter writer, double? value, JsonSerializerOptions options)
    {
        if (value.HasValue)
            writer.WriteNumberValue(value.Value);
        else
            writer.WriteNullValue();
    }
}

namespace Betfair.Models
{
    // Base message classes
    public abstract class RequestMessage
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }
        
        [JsonPropertyName("op")]
        public string Op { get; set; }
    }

    public abstract class ResponseMessage
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }
        
        [JsonPropertyName("op")]
        public string Op { get; set; }
    }

    // Authentication
    public class AuthenticationMessage : RequestMessage
    {
        public AuthenticationMessage()
        {
            // Op will be set by the service when sending
        }

        [JsonPropertyName("appKey")]
        public string AppKey { get; set; }

        [JsonPropertyName("session")]
        public string Session { get; set; }
    }

    // Market Subscription
    public class MarketSubscriptionMessage : RequestMessage
    {
        public MarketSubscriptionMessage()
        {
            Op = "marketSubscription";
        }

        [JsonPropertyName("marketFilter")]
        public MarketFilter MarketFilter { get; set; }

        [JsonPropertyName("marketDataFilter")]
        public MarketDataFilter MarketDataFilter { get; set; }

        [JsonPropertyName("conflateMs")]
        public int? ConflateMs { get; set; }

        [JsonPropertyName("segmentationEnabled")]
        public bool? SegmentationEnabled { get; set; }

        [JsonPropertyName("heartbeatMs")]
        public int? HeartbeatMs { get; set; }

        [JsonPropertyName("initialClk")]
        public string InitialClk { get; set; }

        [JsonPropertyName("clk")]
        public string Clk { get; set; }
    }

    public class MarketFilter
    {
        [JsonPropertyName("marketIds")]
        public List<string> MarketIds { get; set; }

        [JsonPropertyName("eventTypeIds")]
        public List<string> EventTypeIds { get; set; }

        [JsonPropertyName("eventIds")]
        public List<string> EventIds { get; set; }

        [JsonPropertyName("competitionIds")]
        public List<string> CompetitionIds { get; set; }

        [JsonPropertyName("turnInPlayEnabled")]
        public bool? TurnInPlayEnabled { get; set; }

        [JsonPropertyName("marketTypes")]
        public List<string> MarketTypes { get; set; }

        [JsonPropertyName("venues")]
        public List<string> Venues { get; set; }

        [JsonPropertyName("bspMarket")]
        public bool? BspMarket { get; set; }

        [JsonPropertyName("bettingTypes")]
        public List<string> BettingTypes { get; set; }

        [JsonPropertyName("countryCodes")]
        public List<string> CountryCodes { get; set; }

        [JsonPropertyName("raceTypes")]
        public List<string> RaceTypes { get; set; }
    }

    public class MarketDataFilter
    {
        [JsonPropertyName("ladderLevels")]
        public int? LadderLevels { get; set; }

        [JsonPropertyName("fields")]
        public List<string> Fields { get; set; }

        [JsonPropertyName("priceData")]
        public List<string> PriceData { get; set; }

        [JsonPropertyName("virtualise")]
        public bool? Virtualise { get; set; }

        [JsonPropertyName("exBestOffersOverrides")]
        public ExBestOffersOverrides ExBestOffersOverrides { get; set; }
    }

    // Field filter constants as per documentation
    public static class StreamApiFields
    {
        public const string EX_BEST_OFFERS_DISP = "EX_BEST_OFFERS_DISP";
        public const string EX_BEST_OFFERS = "EX_BEST_OFFERS";
        public const string EX_ALL_OFFERS = "EX_ALL_OFFERS";
        public const string EX_TRADED = "EX_TRADED";
        public const string EX_TRADED_VOL = "EX_TRADED_VOL";
        public const string EX_LTP = "EX_LTP";
        public const string EX_MARKET_DEF = "EX_MARKET_DEF";
        public const string SP_TRADED = "SP_TRADED";
        public const string SP_PROJECTED = "SP_PROJECTED";
    }

    public class ExBestOffersOverrides
    {
        [JsonPropertyName("bestPricesDepth")]
        public int? BestPricesDepth { get; set; }

        [JsonPropertyName("rollupModel")]
        public string RollupModel { get; set; }

        [JsonPropertyName("rollupLimit")]
        public int? RollupLimit { get; set; }

        [JsonPropertyName("rollupLiabilityThreshold")]
        public double? RollupLiabilityThreshold { get; set; }

        [JsonPropertyName("rollupLiabilityFactor")]
        public int? RollupLiabilityFactor { get; set; }
    }

    // Order Subscription
    public class OrderSubscriptionMessage : RequestMessage
    {
        public OrderSubscriptionMessage()
        {
            Op = "orderSubscription";
        }

        [JsonPropertyName("orderFilter")]
        public OrderFilter OrderFilter { get; set; }

        [JsonPropertyName("conflateMs")]
        public int? ConflateMs { get; set; }

        [JsonPropertyName("segmentationEnabled")]
        public bool? SegmentationEnabled { get; set; }

        [JsonPropertyName("heartbeatMs")]
        public int? HeartbeatMs { get; set; }

        [JsonPropertyName("initialClk")]
        public string InitialClk { get; set; }

        [JsonPropertyName("clk")]
        public string Clk { get; set; }
    }

    public class OrderFilter
    {
        [JsonPropertyName("includeOverallPosition")]
        public bool? IncludeOverallPosition { get; set; }

        [JsonPropertyName("customerStrategyRefs")]
        public List<string> CustomerStrategyRefs { get; set; }

        [JsonPropertyName("partitionMatchedByStrategyRef")]
        public bool? PartitionMatchedByStrategyRef { get; set; }
    }

    // Heartbeat
    public class HeartbeatMessage : RequestMessage
    {
        public HeartbeatMessage()
        {
            Op = "heartbeat";
        }
    }

    // Response Messages
    public class ConnectionMessage : ResponseMessage
    {
        [JsonPropertyName("connectionId")]
        public string ConnectionId { get; set; }
    }

    public class StatusMessage : ResponseMessage
    {
        [JsonPropertyName("statusCode")]
        public string StatusCode { get; set; }

        [JsonPropertyName("connectionClosed")]
        public bool ConnectionClosed { get; set; }

        [JsonPropertyName("errorCode")]
        public string ErrorCode { get; set; }

        [JsonPropertyName("errorMessage")]
        public string ErrorMessage { get; set; }

        [JsonPropertyName("connectionsAvailable")]
        public int? ConnectionsAvailable { get; set; }
    }

    public class MarketChangeMessage : ResponseMessage
    {
        [JsonPropertyName("clk")]
        public string Clk { get; set; }

        [JsonPropertyName("pt")]
        public long Pt { get; set; }

        [JsonPropertyName("ct")]
        public string Ct { get; set; }

        [JsonPropertyName("status")]
        public int? Status { get; set; }

        [JsonPropertyName("con")]
        public bool? Con { get; set; }

        [JsonPropertyName("mc")]
        public List<MarketChange> MarketChanges { get; set; }
    }

    public class MarketChange
    {
        [JsonPropertyName("id")]
        public string Id { get; set; }

        [JsonPropertyName("marketDefinition")]
        public MarketDefinition MarketDefinition { get; set; }

        [JsonPropertyName("rc")]
        public List<RunnerChange> Rc { get; set; }
    }

    public class MarketDefinition
    {
        [JsonPropertyName("venue")]
        public string Venue { get; set; }

        [JsonPropertyName("raceType")]
        public string RaceType { get; set; }

        [JsonPropertyName("settledTime")]
        public DateTime? SettledTime { get; set; }

        [JsonPropertyName("timezone")]
        public string Timezone { get; set; }

        [JsonPropertyName("eachWayDivisor")]
        public double? EachWayDivisor { get; set; }

        [JsonPropertyName("regulators")]
        public List<string> Regulators { get; set; }

        [JsonPropertyName("marketType")]
        public string MarketType { get; set; }

        [JsonPropertyName("marketBaseRate")]
        public double? MarketBaseRate { get; set; }

        [JsonPropertyName("numberOfWinners")]
        public int? NumberOfWinners { get; set; }

        [JsonPropertyName("countryCode")]
        public string CountryCode { get; set; }

        [JsonPropertyName("lineMaxUnit")]
        public double? LineMaxUnit { get; set; }

        [JsonPropertyName("inPlay")]
        public bool? InPlay { get; set; }

        [JsonPropertyName("betDelay")]
        public int? BetDelay { get; set; }

        [JsonPropertyName("bspMarket")]
        public bool? BspMarket { get; set; }

        [JsonPropertyName("bettingType")]
        public string BettingType { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; }

        [JsonPropertyName("suspendTime")]
        public DateTime? SuspendTime { get; set; }

        [JsonPropertyName("settleTime")]
        public DateTime? SettleTime { get; set; }

        [JsonPropertyName("turnInPlayEnabled")]
        public bool? TurnInPlayEnabled { get; set; }

        [JsonPropertyName("priceLadderDefinition")]
        public PriceLadderDefinition PriceLadderDefinition { get; set; }

        [JsonPropertyName("keyLineDefinition")]
        public KeyLineDefinition KeyLineDefinition { get; set; }

        [JsonPropertyName("openDate")]
        public DateTime? OpenDate { get; set; }

        [JsonPropertyName("marketTime")]
        public DateTime? MarketTime { get; set; }

        [JsonPropertyName("bspReconciled")]
        public bool? BspReconciled { get; set; }

        [JsonPropertyName("complete")]
        public bool? Complete { get; set; }

        [JsonPropertyName("inPlayDelay")]
        public int? InPlayDelay { get; set; }

        [JsonPropertyName("crossMatching")]
        public bool? CrossMatching { get; set; }

        [JsonPropertyName("runnersVoidable")]
        public bool? RunnersVoidable { get; set; }

        [JsonPropertyName("numberOfActiveRunners")]
        public int? NumberOfActiveRunners { get; set; }

        [JsonPropertyName("bettingTypes")]
        public List<string> BettingTypes { get; set; }

        [JsonPropertyName("runners")]
        public List<RunnerDefinition> Runners { get; set; }

        [JsonPropertyName("eventTypeId")]
        public string EventTypeId { get; set; }

        [JsonPropertyName("eventId")]
        public string EventId { get; set; }

        [JsonPropertyName("competition")]
        public StreamCompetition Competition { get; set; }

        [JsonPropertyName("event")]
        public StreamEvent Event { get; set; }
    }

    public class RunnerDefinition
    {
        [JsonPropertyName("sortPriority")]
        public int? SortPriority { get; set; }

        [JsonPropertyName("removalDate")]
        public DateTime? RemovalDate { get; set; }

        [JsonPropertyName("id")]
        public long Id { get; set; }

        [JsonPropertyName("hc")]
        public double? Hc { get; set; }

        [JsonPropertyName("adjustmentFactor")]
        public double? AdjustmentFactor { get; set; }

        [JsonPropertyName("bsp")]
        public double? Bsp { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; }

        [JsonPropertyName("removalReason")]
        public string RemovalReason { get; set; }

        [JsonPropertyName("ltp")]
        public double? Ltp { get; set; }

        [JsonPropertyName("tv")]
        public double? Tv { get; set; }

        [JsonPropertyName("batb")]
        public List<List<double>> Batb { get; set; }

        [JsonPropertyName("batl")]
        public List<List<double>> Batl { get; set; }

        [JsonPropertyName("spb")]
        public List<List<double>> Spb { get; set; }

        [JsonPropertyName("bdatl")]
        public List<List<double>> Bdatl { get; set; }

        [JsonPropertyName("trd")]
        public List<List<double>> Trd { get; set; }

        [JsonPropertyName("spf")]
        [JsonConverter(typeof(NaNSafeDoubleConverter))]
        public double? Spf { get; set; }

        [JsonPropertyName("atl")]
        public List<List<double>> Atl { get; set; }

        [JsonPropertyName("spl")]
        public List<List<double>> Spl { get; set; }

        [JsonPropertyName("spn")]
        [JsonConverter(typeof(NaNSafeDoubleConverter))]
        public double? Spn { get; set; }

        [JsonPropertyName("spc")]
        public double? Spc { get; set; }

        [JsonPropertyName("sl")]
        public double? Sl { get; set; }

        [JsonPropertyName("sc")]
        public double? Sc { get; set; }

        [JsonPropertyName("sn")]
        public double? Sn { get; set; }

        [JsonPropertyName("sel")]
        public bool? Sel { get; set; }
    }

    public class RunnerChange
    {
        [JsonPropertyName("id")]
        public long Id { get; set; }

        [JsonPropertyName("ltp")]
        public double? Ltp { get; set; }

        [JsonPropertyName("tv")]
        public double? Tv { get; set; }

        [JsonPropertyName("batb")]
        public List<List<double>> Batb { get; set; }

        [JsonPropertyName("batl")]
        public List<List<double>> Batl { get; set; }

        [JsonPropertyName("spb")]
        public List<List<double>> Spb { get; set; }

        [JsonPropertyName("bdatl")]
        public List<List<double>> Bdatl { get; set; }

        [JsonPropertyName("trd")]
        public List<List<double>> Trd { get; set; }

        [JsonPropertyName("spf")]
        [JsonConverter(typeof(NaNSafeDoubleConverter))]
        public double? Spf { get; set; }

        [JsonPropertyName("atl")]
        public List<List<double>> Atl { get; set; }

        [JsonPropertyName("spl")]
        public List<List<double>> Spl { get; set; }

        [JsonPropertyName("spn")]
        [JsonConverter(typeof(NaNSafeDoubleConverter))]
        public double? Spn { get; set; }

        [JsonPropertyName("spc")]
        public double? Spc { get; set; }

        [JsonPropertyName("sl")]
        public double? Sl { get; set; }

        [JsonPropertyName("sc")]
        public double? Sc { get; set; }

        [JsonPropertyName("sn")]
        public double? Sn { get; set; }

        [JsonPropertyName("sel")]
        public bool? Sel { get; set; }

        [JsonPropertyName("removalDate")]
        public DateTime? RemovalDate { get; set; }

        [JsonPropertyName("removalReason")]
        public string RemovalReason { get; set; }

        [JsonPropertyName("hc")]
        public double? Hc { get; set; }

        [JsonPropertyName("adjustmentFactor")]
        public double? AdjustmentFactor { get; set; }

        [JsonPropertyName("bsp")]
        public double? Bsp { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; }
    }

    public class OrderChangeMessage : ResponseMessage
    {
        [JsonPropertyName("clk")]
        public string Clk { get; set; }

        [JsonPropertyName("pt")]
        public long Pt { get; set; }

        [JsonPropertyName("ct")]
        public string Ct { get; set; }

        [JsonPropertyName("status")]
        public int? Status { get; set; }

        [JsonPropertyName("con")]
        public bool? Con { get; set; }

        [JsonPropertyName("orderChanges")]
        public List<OrderChange> OrderChanges { get; set; }
    }

    public class OrderChange
    {
        [JsonPropertyName("id")]
        public string Id { get; set; }

        [JsonPropertyName("fullImage")]
        public bool? FullImage { get; set; }

        [JsonPropertyName("oc")]
        public List<Order> Oc { get; set; }

        [JsonPropertyName("or")]
        public List<Order> Or { get; set; }
    }

    public class Order
    {
        [JsonPropertyName("id")]
        public string Id { get; set; }

        [JsonPropertyName("p")]
        public double? P { get; set; }

        [JsonPropertyName("s")]
        public double? S { get; set; }

        [JsonPropertyName("side")]
        public string Side { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; }

        [JsonPropertyName("pt")]
        public long? Pt { get; set; }

        [JsonPropertyName("ot")]
        public string Ot { get; set; }

        [JsonPropertyName("pd")]
        public long? Pd { get; set; }

        [JsonPropertyName("sm")]
        public double? Sm { get; set; }

        [JsonPropertyName("sr")]
        public double? Sr { get; set; }

        [JsonPropertyName("sl")]
        public double? Sl { get; set; }

        [JsonPropertyName("sc")]
        public double? Sc { get; set; }

        [JsonPropertyName("sv")]
        public double? Sv { get; set; }

        [JsonPropertyName("rc")]
        public string Rc { get; set; }

        [JsonPropertyName("rfo")]
        public string Rfo { get; set; }

        [JsonPropertyName("rfs")]
        public string Rfs { get; set; }

        [JsonPropertyName("ld")]
        public long? Ld { get; set; }

        [JsonPropertyName("ls")]
        public double? Ls { get; set; }

        [JsonPropertyName("lss")]
        public double? Lss { get; set; }

        [JsonPropertyName("avp")]
        public double? Avp { get; set; }
    }

    public class PriceLadderDefinition
    {
        [JsonPropertyName("type")]
        public string Type { get; set; }
    }

    public class KeyLineDefinition
    {
        [JsonPropertyName("kl")]
        public List<KeyLineSelection> Kl { get; set; }
    }

    public class KeyLineSelection
    {
        [JsonPropertyName("id")]
        public long Id { get; set; }

        [JsonPropertyName("hc")]
        public double? Hc { get; set; }
    }

    public class StreamCompetition
    {
        [JsonPropertyName("id")]
        public string Id { get; set; }

        [JsonPropertyName("name")]
        public string Name { get; set; }
    }

    public class StreamEvent
    {
        [JsonPropertyName("id")]
        public string Id { get; set; }

        [JsonPropertyName("name")]
        public string Name { get; set; }

        [JsonPropertyName("countryCode")]
        public string CountryCode { get; set; }

        [JsonPropertyName("timezone")]
        public string Timezone { get; set; }

        [JsonPropertyName("venue")]
        public string Venue { get; set; }

        [JsonPropertyName("openDate")]
        public DateTime? OpenDate { get; set; }
    }
}
