using System.Text.Json.Serialization;

namespace Betfair.Models.Runner
{
    public class RunnerFlat
    {
        public long SelectionId { get; set; }
        public double Handicap { get; set; }
        public string Status { get; set; }
        public double? LastPriceTraded { get; set; }
        public double? TotalMatched { get; set; }

        // Flattened Description
        public string RunnerName { get; set; }

        public string MarketName { get; set; }

        public string EventName { get; set; }

        // Flattened Metadata
        public string Form { get; set; }
        public string? WeightValue { get; set; }
        public string? StallDraw { get; set; }
        public string? TrainerName { get; set; }
        public string? OwnerName { get; set; }
        public string? Age { get; set; }
        public string? SireName { get; set; }
        public string? DamName { get; set; }
        public string? Wearing { get; set; }
        public string? JockeyName { get; set; }
        public string? JockeyClaim { get; set; }
        public string? SexType { get; set; }
        public string? DaysSinceLastRun { get; set; }
        public string? SireBred { get; set; }
        public string? DamBred { get; set; }
        public string? DamsireName { get; set; }
        public string? DamsireBred { get; set; }
        public string? DamsireYearBorn { get; set; }
        public string? SireYearBorn { get; set; }
        public string? DamYearBorn { get; set; }
        public string? AdjustedRating { get; set; }
        public string? OfficialRating { get; set; }
        public string? ForecastPriceNumerator { get; set; }
        public string? ForecastPriceDenominator { get; set; }
        public string? Bred { get; set; }
        public string? ColourType { get; set; }
        public string? WeightUnits { get; set; }
        public string? ClothNumber { get; set; }
        public string? ClothNumberAlpha { get; set; }
        public string? ColoursDescription { get; set; }
        public string? ColoursFilename { get; set; }
        public string? MetadataRunnerId { get; set; }
    }


    public class RunnerMetadata
    {
        [JsonPropertyName("FORM")]
        public string? Form { get; set; }

        [JsonPropertyName("WEIGHT_VALUE")]
        public string? WeightValue { get; set; }

        [JsonPropertyName("STALL_DRAW")]
        public string? StallDraw { get; set; }

        [JsonPropertyName("TRAINER_NAME")]
        public string? TrainerName { get; set; }

        [JsonPropertyName("OWNER_NAME")]
        public string? OwnerName { get; set; }

        [JsonPropertyName("AGE")]
        public string? Age { get; set; } // Consider if this should be int?

        [JsonPropertyName("SIRE_NAME")]
        public string? SireName { get; set; }

        [JsonPropertyName("DAM_NAME")]
        public string? DamName { get; set; }

        [JsonPropertyName("WEARING")]
        public string? Wearing { get; set; }

        [JsonPropertyName("JOCKEY_NAME")]
        public string? JockeyName { get; set; }

        [JsonPropertyName("JOCKEY_CLAIM")]
        public string? JockeyClaim { get; set; } // This was null in JSON, so it will still be null in C#

        [JsonPropertyName("SEX_TYPE")]
        public string? SexType { get; set; }

        [JsonPropertyName("DAYS_SINCE_LAST_RUN")]
        public string? DaysSinceLastRun { get; set; }

        [JsonPropertyName("SIRE_BRED")]
        public string? SireBred { get; set; }

        [JsonPropertyName("DAM_BRED")]
        public string? DamBred { get; set; }

        [JsonPropertyName("DAMSIRE_NAME")]
        public string? DamsireName { get; set; }

        [JsonPropertyName("DAMSIRE_BRED")]
        public string? DamsireBred { get; set; }

        [JsonPropertyName("DAMSIRE_YEAR_BORN")]
        public string? DamsireYearBorn { get; set; }

        [JsonPropertyName("SIRE_YEAR_BORN")]
        public string? SireYearBorn { get; set; }

        [JsonPropertyName("DAM_YEAR_BORN")]
        public string? DamYearBorn { get; set; }

        [JsonPropertyName("ADJUSTED_RATING")]
        public string? AdjustedRating { get; set; }

        [JsonPropertyName("OFFICIAL_RATING")]
        public string? OfficialRating { get; set; } // This was null in JSON, so it will still be null in C#

        [JsonPropertyName("FORECASTPRICE_NUMERATOR")]
        public string? ForecastPriceNumerator { get; set; }

        [JsonPropertyName("FORECASTPRICE_DENOMINATOR")]
        public string? ForecastPriceDenominator { get; set; }

        [JsonPropertyName("BRED")]
        public string? Bred { get; set; }

        [JsonPropertyName("COLOUR_TYPE")]
        public string? ColourType { get; set; }

        [JsonPropertyName("WEIGHT_UNITS")]
        public string? WeightUnits { get; set; }

        [JsonPropertyName("CLOTH_NUMBER")]
        public string? ClothNumber { get; set; }

        [JsonPropertyName("CLOTH_NUMBER_ALPHA")]
        public string? ClothNumberAlpha { get; set; }

        [JsonPropertyName("COLOURS_DESCRIPTION")]
        public string? ColoursDescription { get; set; }

        [JsonPropertyName("COLOURS_FILENAME")]
        public string? ColoursFilename { get; set; }

        // SPECIAL CASE: The JSON has "runnerId" (lowercase 'r')
        [JsonPropertyName("runnerId")]
        public string? RunnerId { get; set; }
    }
}
