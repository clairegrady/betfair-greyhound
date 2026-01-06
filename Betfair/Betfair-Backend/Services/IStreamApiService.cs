using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Betfair.Models;

namespace Betfair.Services
{
    public interface IStreamApiService
    {
        Task<bool> ConnectAsync();
        Task DisconnectAsync();
        Task<bool> AuthenticateAsync(string appKey, string sessionToken);
        Task SubscribeToMarketAsync(string marketId, string[] marketFilter = null);
        Task SubscribeToMarketsAsync(List<string> eventTypeIds = null, List<string> marketTypes = null, List<string> countryCodes = null, TimeSpan? timeWindow = null);
        Task SubscribeToOrdersAsync();
        Task UnsubscribeFromMarketAsync(string marketId);
        Task SendHeartbeatAsync();

        bool IsConnected { get; }
        bool IsAuthenticated { get; }

        event EventHandler<MarketChangeEventArgs> MarketChanged;
        event EventHandler<OrderChangeEventArgs> OrderChanged;
        event EventHandler<StatusEventArgs> StatusReceived;
    }

    public class MarketChangeEventArgs : EventArgs
    {
        public string MarketId { get; set; }
        public string ChangeType { get; set; }
        public object MarketData { get; set; }
        public DateTime Timestamp { get; set; }
        public List<StreamRunnerData> Runners { get; set; }
    }
    
    public class StreamRunnerData
    {
        public long SelectionId { get; set; }
        public double? LastTradedPrice { get; set; }
        public List<StreamPriceSize> BestAvailableToBack { get; set; }
        public List<StreamPriceSize> BestAvailableToLay { get; set; }
    }
    
    public class StreamPriceSize
    {
        public double Price { get; set; }
        public double Size { get; set; }
    }

    public class OrderChangeEventArgs : EventArgs
    {
        public string OrderId { get; set; }
        public bool? FullImage { get; set; }
        public List<Order> Orders { get; set; }
        public string ChangeType { get; set; }
        public object OrderData { get; set; }
        public DateTime Timestamp { get; set; }
    }

    public class StatusEventArgs : EventArgs
    {
        public string StatusCode { get; set; }
        public string ErrorCode { get; set; }
        public string ErrorMessage { get; set; }
        public bool ConnectionClosed { get; set; }
        public int? ConnectionsAvailable { get; set; }
    }
}