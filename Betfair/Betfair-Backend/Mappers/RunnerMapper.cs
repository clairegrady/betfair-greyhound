using Betfair.Models.Market;
using Betfair.Models.Runner;

namespace Betfair.Mappers;

public static class RunnerMapper
{
    public static RunnerFlat MapToFlat(RunnerDescription runnerDescription)
    {
        var metadata = runnerDescription.Metadata;

        return new RunnerFlat
        {
            SelectionId = runnerDescription.SelectionId,
            RunnerName = runnerDescription.RunnerName,
            Form = metadata?.Form,
            WeightValue = metadata?.WeightValue,
            StallDraw = metadata?.StallDraw,
            TrainerName = metadata?.TrainerName,
            OwnerName = metadata?.OwnerName,
            Age = metadata?.Age,
            SireName = metadata?.SireName,
            DamName = metadata?.DamName,
            Wearing = metadata?.Wearing,
            JockeyName = metadata?.JockeyName,
            JockeyClaim = metadata?.JockeyClaim,
            SexType = metadata?.SexType,
            DaysSinceLastRun = metadata?.DaysSinceLastRun,
            SireBred = metadata?.SireBred,
            DamBred = metadata?.DamBred,
            DamsireName = metadata?.DamsireName,
            DamsireBred = metadata?.DamsireBred,
            DamsireYearBorn = metadata?.DamsireYearBorn,
            SireYearBorn = metadata?.SireYearBorn,
            DamYearBorn = metadata?.DamYearBorn,
            AdjustedRating = metadata?.AdjustedRating,
            OfficialRating = metadata?.OfficialRating,
            ForecastPriceNumerator = metadata?.ForecastPriceNumerator,
            ForecastPriceDenominator = metadata?.ForecastPriceDenominator,
            Bred = metadata?.Bred,
            ColourType = metadata?.ColourType,
            WeightUnits = metadata?.WeightUnits,
            ClothNumber = metadata?.ClothNumber,
            ClothNumberAlpha = metadata?.ClothNumberAlpha,
            ColoursDescription = metadata?.ColoursDescription,
            ColoursFilename = metadata?.ColoursFilename,
            MetadataRunnerId = metadata?.RunnerId
        };
    }
}
