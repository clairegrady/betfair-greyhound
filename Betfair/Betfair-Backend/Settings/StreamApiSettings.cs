namespace Betfair.Settings
{
    public class StreamApiSettings
    {
        public string StreamUrl { get; set; } = "wss://stream-api.betfair.com:443";
        public string IntegrationStreamUrl { get; set; } = "wss://stream-api-integration.betfair.com:443";
        public bool UseIntegration { get; set; } = false;
        public bool Enabled { get; set; } = true;
        public int HeartbeatIntervalSeconds { get; set; } = 30;
        public int ConnectionTimeoutSeconds { get; set; } = 15;
        public int MaxReconnectAttempts { get; set; } = 5;
        public int ReconnectDelaySeconds { get; set; } = 5;
    }
}
