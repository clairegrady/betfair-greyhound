using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Betfair.Services.RaceResults
{
    /// <summary>
    /// Service for fetching horse racing results from external APIs
    /// </summary>
    public interface IRaceResultsService
    {
        /// <summary>
        /// Get race results for a specific date
        /// </summary>
        Task<List<RaceResult>> GetRaceResultsAsync(DateTime raceDate, string country = "AU");

        /// <summary>
        /// Get race result for a specific race by external race ID
        /// </summary>
        Task<RaceResult> GetRaceResultByIdAsync(string externalRaceId);

        /// <summary>
        /// Search for race results by venue and race name
        /// </summary>
        Task<List<RaceResult>> SearchRaceResultsAsync(string venue, string raceName, DateTime raceDate);

        /// <summary>
        /// Get results for races that finished in the last few hours
        /// </summary>
        Task<List<RaceResult>> GetRecentFinishedRacesAsync(int hoursBack = 4);

        /// <summary>
        /// Check if a race has finished and get its results
        /// </summary>
        Task<RaceResult> CheckRaceStatusAsync(string venue, string raceName, DateTime eventTime);
    }

    /// <summary>
    /// Represents the result of a horse race
    /// </summary>
    public class RaceResult
    {
        public string ExternalRaceId { get; set; }
        public string Venue { get; set; }
        public string RaceName { get; set; }
        public DateTime RaceTime { get; set; }
        public DateTime? ResultTime { get; set; }
        public RaceStatus Status { get; set; }
        public List<HorseFinishingPosition> FinishingPositions { get; set; } = new List<HorseFinishingPosition>();
        public string ResultSource { get; set; } // Which API provided the result
        public Dictionary<string, object> AdditionalData { get; set; } = new Dictionary<string, object>();
        
        /// <summary>
        /// Convert to the format needed for bet settlement
        /// </summary>
        public Dictionary<long, int> ToSelectionResults(Dictionary<string, long> horseNameToSelectionId)
        {
            var results = new Dictionary<long, int>();
            
            foreach (var position in FinishingPositions)
            {
                if (horseNameToSelectionId.TryGetValue(position.HorseName, out long selectionId))
                {
                    results[selectionId] = position.Position;
                }
            }
            
            return results;
        }
    }

    /// <summary>
    /// Horse finishing position in a race
    /// </summary>
    public class HorseFinishingPosition
    {
        public string HorseName { get; set; }
        public int Position { get; set; }
        public string Jockey { get; set; }
        public decimal? StartingPrice { get; set; }
        public string Comments { get; set; }
        public bool IsNonRunner { get; set; }
        
        /// <summary>
        /// Alternative horse names for matching (some sources use different names)
        /// </summary>
        public List<string> AlternativeNames { get; set; } = new List<string>();
    }

    public enum RaceStatus
    {
        NotStarted,
        InProgress,
        Finished,
        Abandoned,
        Postponed,
        Unknown
    }
}
