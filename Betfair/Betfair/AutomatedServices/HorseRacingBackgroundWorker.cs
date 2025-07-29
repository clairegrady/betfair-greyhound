using Betfair.AutomationServices;
using Betfair.Models.Market;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Microsoft.Extensions.Hosting;

namespace Betfair.Services
{
    public class HorseRacingStartupService : BackgroundService
    {
        private readonly HorseRacingAutomationService _horseRacingAutomationService;
        private readonly OrderService _orderService;
        private readonly AccountService _accountService;
        private readonly HistoricalDataService _historicalDataService;

        public HorseRacingStartupService(
            HorseRacingAutomationService horseRacingAutomationService,
            OrderService orderService,
            AccountService accountService,
            HistoricalDataService historicalDataService)
        {
            _horseRacingAutomationService = horseRacingAutomationService;
            _orderService = orderService;
            _accountService = accountService;
            _historicalDataService = historicalDataService;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                // Fetch and process all current horse racing market catalogues dynamically
                var marketCatalogues = await _horseRacingAutomationService.GetAndProcessHorseRacingMarketCataloguesAsync();

                var marketIds = marketCatalogues.Select(m => m.MarketId).ToList();

                if (marketIds.Any())
                {
                    // Fetch and process market books for these market IDs
                    await _horseRacingAutomationService.ProcessHorseMarketBooksAsync(marketIds);
                }

                // TODO: Add additional logic here, e.g., place orders, check account funds, etc.

                // Wait 2 minutes before the next iteration
                await Task.Delay(TimeSpan.FromMinutes(2), stoppingToken);
            }
        }
    }
}
