using Betfair.Models.Market;
using Betfair.Models.Runner;

namespace Betfair.Services.Interfaces
{
    public interface IResultsService
    {
        Task<List<MarketBook<ApiRunner>>> GetSettledMarkets(List<string> marketIds);
    }
}
