using System.Collections.Generic;

namespace Betfair.Models.Data;

public class HistoricalDataRequest
{
    public string Sport { get; set; }
    public string Plan { get; set; }
    public int FromDay { get; set; }
    public int FromMonth { get; set; }
    public int FromYear { get; set; }
    public int ToDay { get; set; }
    public int ToMonth { get; set; }
    public int ToYear { get; set; }
    public List<string> MarketTypes { get; set; }
    public List<string> Countries { get; set; }

    // Constructor to initialize the object with the provided values
    public HistoricalDataRequest(string sport, string plan, int fromDay, int fromMonth, int fromYear,
        int toDay, int toMonth, int toYear, List<string> marketTypes, List<string> countries)
    {
        Sport = sport;
        Plan = plan;
        FromDay = fromDay;
        FromMonth = fromMonth;
        FromYear = fromYear;
        ToDay = toDay;
        ToMonth = toMonth;
        ToYear = toYear;
        MarketTypes = marketTypes ?? new List<string>();
        Countries = countries ?? new List<string>();
    }
}
