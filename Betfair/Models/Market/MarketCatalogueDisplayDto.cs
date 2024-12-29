namespace Betfair.Models.Market;
public class MarketCatalogueDisplayDto
{
    public string MarketId { get; set; }
    public string MarketName { get; set; }
    public double TotalMatched { get; set; }
    public EventDisplayDto Event { get; set; }
    public EventTypeDisplayDto EventType { get; set; }
    public CompetitionDisplayDto Competition { get; set; }
}

public class EventDisplayDto
{
    public string EventId { get; set; }
    public string EventName { get; set; }
    public string CountryCode { get; set; }
    public string Timezone { get; set; }
    public DateTime OpenDate { get; set; }
}

public class EventTypeDisplayDto
{
    public string EventTypeId { get; set; }
    public string EventTypeName { get; set; }
}

public class CompetitionDisplayDto
{
    public string CompetitionId { get; set; }
    public string CompetitionName { get; set; }
}
