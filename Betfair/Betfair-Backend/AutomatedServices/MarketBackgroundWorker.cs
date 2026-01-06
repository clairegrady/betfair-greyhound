using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Betfair.AutomationServices;

namespace Betfair.AutomatedServices
{
    public class MarketBackgroundWorker : BackgroundService
    {
        private readonly MarketAutomationService _marketAutomationService;
        private readonly string _eventId;
        private readonly string _competitionId;

        public MarketBackgroundWorker(MarketAutomationService marketAutomationService, string eventId = null, string competitionId = null)
        {
            _marketAutomationService = marketAutomationService;
            _eventId = eventId;
            _competitionId = competitionId;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            Console.WriteLine("MarketBackgroundWorker started...");
            Console.WriteLine($"EventId: {_eventId}, CompetitionId: {_competitionId}");
            
            // Wait 15 seconds for network to be ready
            Console.WriteLine("⏳ Waiting 15 seconds for network initialization...");
            await Task.Delay(15000, stoppingToken);

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    Console.WriteLine("Starting market processing cycle...");

                    // Fetch and process market catalogues
                    Console.WriteLine("Calling ProcessMarketCataloguesAsync...");
                    var marketDetails = await _marketAutomationService.ProcessMarketCataloguesAsync(_eventId, _competitionId);
                    Console.WriteLine($"Retrieved {marketDetails.Count} market details");

                    var marketIds = marketDetails.Select(md => md.MarketId).ToList();
                    Console.WriteLine($"Market IDs to process: {string.Join(", ", marketIds)}");

                    // Fetch and process market books
                    if (marketIds.Any())
                    {
                        Console.WriteLine($"Processing {marketIds.Count} market books...");
                        await _marketAutomationService.ProcessMarketBooksAsync(marketIds);
                        Console.WriteLine("Market books processing completed");
                    }
                    else
                    {
                        Console.WriteLine("No market IDs found, skipping market books processing");
                    }

                    Console.WriteLine("Waiting 2 minutes before next cycle...");
                    await Task.Delay(TimeSpan.FromSeconds(900), stoppingToken);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Error in MarketBackgroundWorker: {ex.Message}");
                    Console.WriteLine($"Stack trace: {ex.StackTrace}");
                    await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken); // Wait 30 seconds before retrying
                }
            }
        }
    }
}