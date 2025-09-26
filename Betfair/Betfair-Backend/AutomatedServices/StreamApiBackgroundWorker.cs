using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Betfair.Services;
using Betfair.Services.Account;
using Betfair.Settings;

namespace Betfair.AutomatedServices
{
    public class StreamApiBackgroundWorker : BackgroundService
    {
        private readonly ILogger<StreamApiBackgroundWorker> _logger;
        private readonly IStreamApiService _streamApiService;
        private readonly BetfairAuthService _authService;
        private readonly StreamApiAuthService _streamApiAuthService;
        private readonly IOptions<AuthSettings> _authSettings;
        private readonly StreamApiSettings _settings;
        private Timer _heartbeatTimer;
        private readonly List<string> _subscribedMarkets = new();

        public StreamApiBackgroundWorker(
            ILogger<StreamApiBackgroundWorker> logger,
            IStreamApiService streamApiService,
            BetfairAuthService authService,
            StreamApiAuthService streamApiAuthService,
            IOptions<AuthSettings> authSettings,
            IOptions<StreamApiSettings> settings)
        {
            _logger = logger;
            _streamApiService = streamApiService;
            _authService = authService;
            _streamApiAuthService = streamApiAuthService;
            _authSettings = authSettings;
            _settings = settings.Value;
            _logger.LogWarning("🔧 StreamApiBackgroundWorker constructor called");
            _logger.LogWarning("🔧 StreamApiBackgroundWorker constructor completed");
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogWarning("🚀 StreamApiBackgroundWorker ExecuteAsync called");
            _logger.LogWarning("Stream API Background Worker started");

            // Check if Stream API is enabled
            if (!_settings.Enabled)
            {
                _logger.LogInformation("Stream API is disabled in configuration");
                return;
            }

            // Try to initialize Stream API, but don't fail if it's not available
            try
            {
                await InitializeStreamApiAsync();
                await MonitorStreamConnectionAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Stream API not available, continuing without real-time updates");
                
                // Continue running but without Stream API
                while (!stoppingToken.IsCancellationRequested)
                {
                    await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
                }
            }
        }

        private async Task InitializeStreamApiAsync()
        {
            // Subscribe to events
            _streamApiService.MarketChanged += OnMarketChanged;
            _streamApiService.OrderChanged += OnOrderChanged;
            _streamApiService.StatusReceived += OnStatusReceived;

            // Debug: Check what AppKey we're getting
            _logger.LogWarning($"Retrieved AppKey from configuration: '{_authSettings.Value.AppKey}'");
            _logger.LogWarning($"AppKey length: {_authSettings.Value.AppKey?.Length ?? 0}");

            // Connect to Stream API
            _logger.LogInformation("Connecting to Stream API...");
            var connected = await _streamApiService.ConnectAsync();
            if (!connected)
            {
                throw new Exception("Failed to connect to Stream API");
            }

            _logger.LogWarning("Successfully connected to Stream API");

            if (string.IsNullOrEmpty(_authSettings.Value.AppKey))
            {
                throw new Exception("AppKey is null or empty in configuration");
            }

        //Get session token using regular BetfairAuthService (same as other APIs)
        _logger.LogWarning("Getting session token for Stream API authentication...");
        var sessionToken = await _authService.GetSessionTokenAsync();
        _logger.LogWarning($"Retrieved session token: {sessionToken?.Substring(0, Math.Min(10, sessionToken?.Length ?? 0))}...");

        if (string.IsNullOrEmpty(sessionToken))
        {
            throw new Exception("Failed to retrieve session token from BetfairAuthService");
        }
        
        // Authenticate with Stream API using same auth as other APIs
        _logger.LogWarning($"=== CALLING AUTHENTICATEASYNC ===");
        _logger.LogWarning($"Authenticating with Stream API using AppKey: '{_authSettings.Value.AppKey}' and SessionToken: '{sessionToken?.Substring(0, Math.Min(10, sessionToken?.Length ?? 0))}...'");
        
        if (string.IsNullOrEmpty(_authSettings.Value.AppKey))
        {
            _logger.LogError("CRITICAL: AppKey is null or empty in StreamApiBackgroundWorker!");
            throw new Exception("AppKey is null or empty");
        }
        
        var authenticated = await _streamApiService.AuthenticateAsync(
            _authSettings.Value.AppKey,
            sessionToken
        );
        
        _logger.LogWarning($"=== AUTHENTICATEASYNC COMPLETED: {authenticated} ===");

            if (!authenticated)
            {
                _logger.LogError("Stream API authentication failed - disconnecting and throwing exception");
                await _streamApiService.DisconnectAsync();
                throw new Exception("Failed to authenticate with Stream API");
            }

            _logger.LogWarning("Stream API authentication successful");

            // Subscribe to orders
            await _streamApiService.SubscribeToOrdersAsync();

            // Start heartbeat timer
            _heartbeatTimer = new Timer(SendHeartbeat, null, 
                TimeSpan.FromSeconds(_settings.HeartbeatIntervalSeconds), 
                TimeSpan.FromSeconds(_settings.HeartbeatIntervalSeconds));

            _logger.LogInformation("Stream API initialized successfully");
        }

        private async Task MonitorStreamConnectionAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                if (!_streamApiService.IsConnected || !_streamApiService.IsAuthenticated)
                {
                    _logger.LogWarning("Stream API connection lost or not authenticated, attempting to reconnect...");
                    await ReconnectAsync();
                }

                await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
            }
        }

        private async Task ReconnectAsync()
        {
            var attempts = 0;
            while (attempts < _settings.MaxReconnectAttempts)
            {
                try
                {
                    await _streamApiService.DisconnectAsync();
                    await Task.Delay(TimeSpan.FromSeconds(_settings.ReconnectDelaySeconds));
                    
                    var connected = await _streamApiService.ConnectAsync();
                    if (connected)
                    {
                        // Re-authenticate after reconnection using regular auth service
                        var sessionToken = await _authService.GetSessionTokenAsync();
                        var authenticated = await _streamApiService.AuthenticateAsync(_authSettings.Value.AppKey, sessionToken);
                        
                        if (authenticated)
                        {
                            _logger.LogInformation("Stream API reconnected and authenticated successfully");
                            return;
                        }
                        else
                        {
                            _logger.LogWarning("Stream API reconnected but authentication failed");
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, $"Reconnection attempt {attempts + 1} failed");
                }

                attempts++;
            }

            _logger.LogError("Failed to reconnect to Stream API after maximum attempts");
        }

        private async void SendHeartbeat(object state)
        {
            try
            {
                if (_streamApiService?.IsConnected == true)
                {
                    await _streamApiService.SendHeartbeatAsync();
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error sending heartbeat");
            }
        }

        private void OnMarketChanged(object sender, MarketChangeEventArgs e)
        {
            _logger.LogInformation($"Market change received for {e.MarketId}: {e.ChangeType}");
            
            // Process market changes here
            // You can update your database with real-time market data
            // This is where you'd integrate with your existing market data handling
        }

        private void OnOrderChanged(object sender, OrderChangeEventArgs e)
        {
            _logger.LogInformation($"Order change received for {e.OrderId}: {e.ChangeType}");
            
            // Process order changes here
            // Update your order status in the database
            // This is where you'd integrate with your existing order handling
        }

        private void OnStatusReceived(object sender, StatusEventArgs e)
        {
            _logger.LogInformation($"Status received: {e.StatusCode}");
            
            if (e.ConnectionClosed)
            {
                _logger.LogWarning("Stream API connection closed by server");
            }
        }

        public async Task SubscribeToMarketAsync(string marketId)
        {
            if (_streamApiService?.IsConnected == true)
            {
                await _streamApiService.SubscribeToMarketAsync(marketId);
                _subscribedMarkets.Add(marketId);
                _logger.LogInformation($"Subscribed to market {marketId}");
            }
        }

        public async Task UnsubscribeFromMarketAsync(string marketId)
        {
            if (_streamApiService?.IsConnected == true)
            {
                await _streamApiService.UnsubscribeFromMarketAsync(marketId);
                _subscribedMarkets.Remove(marketId);
                _logger.LogInformation($"Unsubscribed from market {marketId}");
            }
        }

        public override async Task StopAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Stream API Background Worker stopping");

            _heartbeatTimer?.Dispose();
            
            if (_streamApiService != null)
            {
                _streamApiService.MarketChanged -= OnMarketChanged;
                _streamApiService.OrderChanged -= OnOrderChanged;
                _streamApiService.StatusReceived -= OnStatusReceived;
                await _streamApiService.DisconnectAsync();
            }

            await base.StopAsync(cancellationToken);
        }
    }
}
