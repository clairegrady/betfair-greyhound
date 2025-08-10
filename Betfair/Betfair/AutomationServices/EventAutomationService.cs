using System.Text.Json;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Event;
using Betfair.Services;

namespace Betfair.AutomationServices;
public class EventAutomationService
{
    private readonly IEventService _eventService;
    private readonly EventDb2 _eventDb;

    public EventAutomationService(IEventService eventService, EventDb2 eventDb)
    {
        _eventService = eventService;
        _eventDb = eventDb;
    }
    public async Task FetchAndStoreEventTypeAsync()
    {
        var eventTypesJson = await _eventService.ListEventTypes();
        var eventTypesApiResponse = JsonSerializer.Deserialize<ApiResponse<EventTypeResult>>(eventTypesJson);
        if (eventTypesApiResponse?.Result != null)
        {
            var eventTypes = eventTypesApiResponse.Result
                .Select(e => new EventTypeResult
                {
                    EventType = new EventType
                    {
                        Id = e.EventType.Id,
                        Name = e.EventType.Name
                    },
                    MarketCount = e.MarketCount 
                })
                .ToList();
            
            if (eventTypes.Any())
            {
                await _eventDb.InsertEventTypesAsync(eventTypes);
            }
            else
            {
                //Console.WriteLine("No event types to insert.");
            }
        }
        else
        {
            //Console.WriteLine("Failed to deserialize event types.");
        }
    }
    public async Task<List<EventListResult>> FetchAndStoreListOfEventsAsync(List<string> eventIds)
    {
        var eventListJson = await _eventService.ListEvents(eventIds);
        var eventListApiResponse = JsonSerializer.Deserialize<ApiResponse<EventListResult>>(eventListJson);

        if (eventListApiResponse?.Result != null)
        {
            var eventList = eventListApiResponse.Result
                .Select(e => new EventListResult
                {
                    Event = new Event
                    {
                        Id = e.Event.Id,
                        Name = e.Event.Name,
                        CountryCode = e.Event.CountryCode,
                        Timezone = e.Event.Timezone,
                        OpenDate = e.Event.OpenDate
                    },
                    MarketCount = e.MarketCount
                })
                .ToList();

            if (eventList.Any())
            {
                await _eventDb.InsertEventListAsync(eventList, "Horse Racing");
            }
            else
            {
                //Console.WriteLine("No events to insert.");
            }

            return eventList;
        }
        else
        {
            //Console.WriteLine("Failed to deserialize event list.");
            return new List<EventListResult>();
        }
    }

}