using System.Text;
using System.Text.Json;
using Betfair.Models.Account;
using Betfair.Models.Orders;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services.Account
{
    public class PlaceOrderService : IPlaceOrderService
    {
        private readonly HttpClient _httpClient;
        private readonly BetfairAuthService _authService;
        private readonly EndpointSettings _settings;
        private string _sessionToken;

        public PlaceOrderService(HttpClient httpClient, BetfairAuthService authService,
            IOptions<EndpointSettings> options)
        {
            _httpClient = httpClient;
            _authService = authService;
            _settings = options.Value;
        }

        public async Task<string> PlaceOrdersAsync(PlaceOrderRequest request)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var placeOrdersRequest = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/placeOrders",
                @params = new
                {
                    marketId = request.MarketId,
                    instructions = request.Instructions.Select(i => new
                    {
                        selectionId = i.SelectionId,
                        side = i.Side,
                        orderType = i.OrderType,
                        limitOrder = i.LimitOrder != null
                            ? new
                            {
                                size = i.LimitOrder.Size,
                                price = i.LimitOrder.Price,
                                persistenceType = i.LimitOrder.PersistenceType
                            }
                            : null,
                        limitOnCloseOrder = i.LimitOnCloseOrder != null
                            ? new
                            {
                                price = i.LimitOnCloseOrder.Price,
                                liability = i.LimitOnCloseOrder.Liability
                            }
                            : null,
                        marketOnCloseOrder = i.MarketOnCloseOrder,
                        persistenceType = i.PersistenceType,
                        timeInForce = i.TimeInForce,
                        minFillSize = i.MinFillSize
                    }).ToArray()
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(placeOrdersRequest), Encoding.UTF8,
                "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new HttpRequestException($"Error placing order: {response.StatusCode} - {errorContent}");
            }

            return await response.Content.ReadAsStringAsync();
        }

        public async Task<string> CancelOrderAsync(string marketId, List<CancelInstruction> instructions,
            string customerRef = null)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var cancelOrdersRequest = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/cancelOrders",
                @params = new
                {
                    marketId,
                    instructions,
                    customerRef
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(cancelOrdersRequest), Encoding.UTF8,
                "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new HttpRequestException($"Error canceling order(s): {response.StatusCode} - {errorContent}");
            }

            return await response.Content.ReadAsStringAsync();
        }

        public async Task<string> UpdateOrdersAsync(string marketId, List<UpdateInstruction> instructions,
            string customerRef = null)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var updateOrdersRequest = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/updateOrders",
                @params = new
                {
                    marketId,
                    instructions,
                    customerRef
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(updateOrdersRequest), Encoding.UTF8,
                "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new HttpRequestException($"Error updating orders: {response.StatusCode} - {errorContent}");
            }

            return await response.Content.ReadAsStringAsync();
        }

        public async Task<string> ReplaceOrdersAsync(string marketId, List<ReplaceInstruction> instructions,
            string customerRef = null, MarketVersion marketVersion = null, bool async = false)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var replaceOrdersRequest = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/replaceOrders",
                @params = new
                {
                    marketId,
                    instructions,
                    customerRef,
                    marketVersion,
                    async
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(replaceOrdersRequest), Encoding.UTF8,
                "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new HttpRequestException($"Error replacing orders: {response.StatusCode} - {errorContent}");
            }

            return await response.Content.ReadAsStringAsync();
        }

        public async Task<CurrentOrderSummaryReport> ListCurrentOrdersAsync(
            List<string> betIds = null,
            List<string> marketIds = null,
            string orderProjection = null,
            string dateRangeFrom = null,
            string dateRangeTo = null,
            string orderBy = null,
            string sortDir = null,
            int? fromRecord = null,
            int? recordCount = null,
            bool includeItemDescription = false,
            bool includeSourceId = false)
        {
            _sessionToken = await _authService.GetSessionTokenAsync();

            var listCurrentOrdersRequest = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listCurrentOrders",
                @params = new
                {
                    betIds,
                    marketIds,
                    orderProjection,
                    dateRange = (dateRangeFrom != null || dateRangeTo != null)
                        ? new { from = dateRangeFrom, to = dateRangeTo }
                        : null,
                    orderBy,
                    sortDir,
                    fromRecord,
                    recordCount,
                    includeItemDescription,
                    includeSourceId
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Remove("X-Authentication");
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", _sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(listCurrentOrdersRequest), Encoding.UTF8,
                "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new HttpRequestException($"Error listing current orders: {response.StatusCode} - {errorContent}");
            }

            var json = await response.Content.ReadAsStringAsync();

            using var doc = JsonDocument.Parse(json);
            var resultElement = doc.RootElement.GetProperty("result");

            return JsonSerializer.Deserialize<CurrentOrderSummaryReport>(resultElement.GetRawText());
        }
    }

    public interface IPlaceOrderService
    {
        Task<string> PlaceOrdersAsync(PlaceOrderRequest request);
        Task<string> CancelOrderAsync(string marketId, List<CancelInstruction> instructions, string customerRef = null);
        Task<string> UpdateOrdersAsync(string marketId, List<UpdateInstruction> instructions, string customerRef = null);
        Task<string> ReplaceOrdersAsync(string marketId, List<ReplaceInstruction> instructions, string customerRef = null, MarketVersion marketVersion = null, bool async = false);
        Task<CurrentOrderSummaryReport> ListCurrentOrdersAsync(List<string> betIds = null, List<string> marketIds = null, string orderProjection = null,
            string dateRangeFrom = null, string dateRangeTo = null, string orderBy = null, string sortDir = null,
            int? fromRecord = null, int? recordCount = null, bool includeItemDescription = false, bool includeSourceId = false);
    }
}
