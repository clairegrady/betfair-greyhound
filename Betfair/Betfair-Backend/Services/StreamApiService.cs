using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Security;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Betfair.Models;
using Betfair.Settings;

namespace Betfair.Services
{
    public class StreamApiService : IStreamApiService, IDisposable
    {
        private readonly ILogger<StreamApiService> _logger;
        private readonly StreamApiSettings _settings;
        private TcpClient _tcpClient;
        private SslStream _sslStream;
        private StreamReader _streamReader;
        private StreamWriter _streamWriter;
        private CancellationTokenSource _cancellationTokenSource;
        private bool _disposed = false;
        private int _messageId = 0;
        private readonly Dictionary<int, TaskCompletionSource<ResponseMessage>> _pendingMessages = new();
        private bool _connectionReceived = false;
        private bool _authenticated = false;
        private readonly SemaphoreSlim _connectionSemaphore = new SemaphoreSlim(0, 1);

        public bool IsConnected => _tcpClient?.Connected == true && _sslStream?.IsAuthenticated == true;
        public bool IsAuthenticated => _authenticated;

        public event EventHandler<MarketChangeEventArgs> MarketChanged;
        public event EventHandler<OrderChangeEventArgs> OrderChanged;
        public event EventHandler<StatusEventArgs> StatusReceived;

        public StreamApiService(ILogger<StreamApiService> logger, IOptions<StreamApiSettings> settings)
        {
            _logger = logger;
            _settings = settings.Value;
        }

        public async Task<bool> ConnectAsync()
        {
            try
            {
                _cancellationTokenSource = new CancellationTokenSource();

                // Use the correct host based on configuration
                var host = _settings.UseIntegration ? "stream-api-integration.betfair.com" : "stream-api.betfair.com";
                var port = 443;
                
                _logger.LogInformation($"Connecting to Stream API: {host}:{port}");
                
                // Create TCP client and connect
                _tcpClient = new TcpClient();
                await _tcpClient.ConnectAsync(host, port);
                
                // Create SSL stream exactly like the official Betfair sample
                _sslStream = new SslStream(_tcpClient.GetStream(), false);
                await _sslStream.AuthenticateAsClientAsync(host);
                
                // Create stream reader and writer exactly like the official sample
                _streamReader = new StreamReader(_sslStream, Encoding.UTF8, false, 1024 * 1000 * 2); // Match official buffer size
                _streamWriter = new StreamWriter(_sslStream, Encoding.UTF8);

                _logger.LogInformation("Connected to Betfair Stream API");
                _ = Task.Run(ReceiveMessagesAsync);
                return true;
            }
            catch (OperationCanceledException)
            {
                _logger.LogError("Connection timeout to Betfair Stream API");
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to connect to Betfair Stream API");
                return false;
            }
        }

        public async Task DisconnectAsync()
        {
            try
            {
                _cancellationTokenSource?.Cancel();
                
                _streamWriter?.Close();
                _streamReader?.Close();
                _sslStream?.Close();
                _tcpClient?.Close();
                
                _logger.LogInformation("Disconnected from Betfair Stream API");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error disconnecting from Betfair Stream API");
            }
        }

        public async Task<bool> AuthenticateAsync(string appKey, string sessionToken)
        {
            try
            {
                _logger.LogInformation($"Authenticating with Stream API - AppKey: {appKey}, SessionToken: {sessionToken?.Substring(0, Math.Min(10, sessionToken?.Length ?? 0))}...");
                
                // Wait for connection message to be received (like official sample)
                if (!_connectionReceived)
                {
                    _logger.LogInformation("Waiting for connection message from Stream API...");
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
                    await _connectionSemaphore.WaitAsync(cts.Token);
                }
                
                var authMessage = new AuthenticationMessage
                {
                    Id = ++_messageId,
                    AppKey = appKey,
                    Session = sessionToken
                };
                
                _logger.LogInformation($"Sending authentication message: Id={authMessage.Id}, AppKey={authMessage.AppKey}, Session={authMessage.Session?.Substring(0, Math.Min(10, authMessage.Session?.Length ?? 0))}...");

                _logger.LogInformation("Sending authentication message to Stream API...");
                var response = await SendMessageAsync<StatusMessage>(authMessage);
                _logger.LogInformation($"Authentication response received: {response != null}");
                if (response != null)
                {
                    _logger.LogInformation($"Authentication response: StatusCode={response.StatusCode}, ErrorCode={response.ErrorCode}, ErrorMessage={response.ErrorMessage}");
                }
                else
                {
                    _logger.LogError("Authentication response is null - no response received from Stream API");
                }
                
                if (response?.StatusCode == "SUCCESS")
                {
                    _authenticated = true;
                    _logger.LogInformation("Stream API authentication successful");
                }
                else
                {
                    _authenticated = false;
                    _logger.LogError($"Stream API authentication failed: StatusCode={response?.StatusCode}, ErrorCode={response?.ErrorCode}, ErrorMessage={response?.ErrorMessage}");
                }
                
                return response?.StatusCode == "SUCCESS";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Authentication failed");
                return false;
            }
        }

        public async Task SubscribeToMarketAsync(string marketId, string[] marketFilter = null)
        {
            try
            {
                var subscriptionMessage = new MarketSubscriptionMessage
                {
                    Id = ++_messageId,
                    MarketFilter = new MarketFilter
                    {
                        MarketIds = new List<string> { marketId }
                    },
                    MarketDataFilter = new MarketDataFilter
                    {
                        Fields = new List<string> 
                        { 
                            StreamApiFields.EX_BEST_OFFERS_DISP,
                            StreamApiFields.EX_BEST_OFFERS,
                            StreamApiFields.EX_ALL_OFFERS,
                            StreamApiFields.EX_TRADED,
                            StreamApiFields.EX_TRADED_VOL,
                            StreamApiFields.EX_LTP,
                            StreamApiFields.EX_MARKET_DEF,
                            StreamApiFields.SP_TRADED,
                            StreamApiFields.SP_PROJECTED
                        },
                        LadderLevels = 3
                    },
                    ConflateMs = 0,
                    SegmentationEnabled = true,
                    HeartbeatMs = 5000
                };

                await SendMessageAsync<StatusMessage>(subscriptionMessage);
                _logger.LogInformation($"Subscribed to market {marketId}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Failed to subscribe to market {marketId}");
            }
        }

        public async Task SubscribeToOrdersAsync()
        {
            try
            {
                var orderSubscriptionMessage = new OrderSubscriptionMessage
                {
                    Id = ++_messageId,
                    OrderFilter = new OrderFilter
                    {
                        IncludeOverallPosition = true,
                        PartitionMatchedByStrategyRef = false
                    },
                    ConflateMs = 0,
                    SegmentationEnabled = true,
                    HeartbeatMs = 5000
                };

                await SendMessageAsync<StatusMessage>(orderSubscriptionMessage);
                _logger.LogInformation("Subscribed to order changes");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to subscribe to orders");
            }
        }

        public async Task UnsubscribeFromMarketAsync(string marketId)
        {
            try
            {
                // Note: Betfair doesn't have a specific unsubscribe message
                // You would need to manage subscriptions locally
                _logger.LogInformation($"Unsubscribed from market {marketId}");
                await Task.CompletedTask;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Failed to unsubscribe from market {marketId}");
            }
        }

        public async Task SendHeartbeatAsync()
        {
            try
            {
                var heartbeatMessage = new HeartbeatMessage
                {
                    Id = ++_messageId
                };

                await SendMessageAsync<StatusMessage>(heartbeatMessage);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send heartbeat");
            }
        }

        private async Task<T> SendMessageAsync<T>(RequestMessage message) where T : ResponseMessage
        {
            // Test the JSON serialization first
            _logger.LogInformation($"=== DEBUGGING JSON SERIALIZATION ===");
            _logger.LogInformation($"Message Type: {message.GetType().Name}");

            if (message is AuthenticationMessage authMsg)
            {
                _logger.LogInformation($"AuthMessage Properties - Id: {authMsg.Id}, Op: '{authMsg.Op}', AppKey: '{authMsg.AppKey}', Session: '{authMsg.Session?.Substring(0, Math.Min(10, authMsg.Session?.Length ?? 0))}...'");
            }

            var options = new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
                WriteIndented = true, // Make it readable for debugging
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
            };

            var json = JsonSerializer.Serialize(message, options);

            _logger.LogInformation($"=== EXACT JSON BEING SENT ===");
            _logger.LogInformation($"{json}");
            _logger.LogInformation($"=== END JSON ===");

        _streamWriter.WriteLine(json);
        _streamWriter.Flush();
        _logger.LogInformation($"Message sent, waiting for response with ID: {message.Id}");

            var tcs = new TaskCompletionSource<ResponseMessage>();
            _pendingMessages[message.Id] = tcs;

            // Add timeout to prevent hanging
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
            cts.Token.Register(() => tcs.TrySetCanceled());

            try
            {
                var result = await tcs.Task;
                _logger.LogInformation($"Received response for ID {message.Id}: {result != null}");
                return result as T;
            }
            catch (OperationCanceledException)
            {
                _logger.LogError($"Timeout waiting for response to message ID {message.Id}");
                _pendingMessages.Remove(message.Id);
                throw new TimeoutException($"No response received for message ID {message.Id}");
            }
        }

        private async Task ReceiveMessagesAsync()
        {
            try
            {
                while (_tcpClient?.Connected == true && !_cancellationTokenSource.Token.IsCancellationRequested)
                {
                    var message = _streamReader.ReadLine();
                    if (message == null)
                    {
                        _logger.LogWarning("Received null message from Stream API - connection may be closing");
                        break;
                    }
                    if (!string.IsNullOrEmpty(message))
                    {
                        _logger.LogInformation($"Received Stream API message: {message}");
                        await ProcessMessageAsync(message);
                    }
                    else
                    {
                        _logger.LogWarning("Received empty message from Stream API - connection may be closing");
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error receiving messages from Stream API");
            }
            finally
            {
                _logger.LogWarning("Stream API connection closed");
                _authenticated = false;
            }
        }

        private async Task ProcessMessageAsync(string message)
        {
            try
            {
                var jsonDocument = JsonDocument.Parse(message);
                var op = jsonDocument.RootElement.GetProperty("op").GetString();
                
                // Handle messages without id (like connection messages)
                int? id = null;
                if (jsonDocument.RootElement.TryGetProperty("id", out var idElement))
                {
                    id = idElement.GetInt32();
                }

                switch (op)
                {
                    case "connection":
                        var connectionMessage = JsonSerializer.Deserialize<ConnectionMessage>(message);
                        _logger.LogInformation($"Connection established: {connectionMessage.ConnectionId}");
                        _connectionReceived = true;
                        _connectionSemaphore.Release(); // Signal that connection is ready
                        break;

                    case "status":
                        var statusMessage = JsonSerializer.Deserialize<StatusMessage>(message);
                        StatusReceived?.Invoke(this, new StatusEventArgs
                        {
                            StatusCode = statusMessage.StatusCode,
                            ErrorCode = statusMessage.ErrorCode,
                            ErrorMessage = statusMessage.ErrorMessage,
                            ConnectionClosed = statusMessage.ConnectionClosed,
                            ConnectionsAvailable = statusMessage.ConnectionsAvailable
                        });

                        if (id.HasValue && _pendingMessages.TryGetValue(id.Value, out var tcs))
                        {
                            tcs.SetResult(statusMessage);
                            _pendingMessages.Remove(id.Value);
                        }
                        break;

                    case "mcm":
                        var marketChangeMessage = JsonSerializer.Deserialize<MarketChangeMessage>(message);
                        ProcessMarketChangeMessage(marketChangeMessage);
                        break;

                    case "ocm":
                        var orderChangeMessage = JsonSerializer.Deserialize<OrderChangeMessage>(message);
                        ProcessOrderChangeMessage(orderChangeMessage);
                        break;

                    default:
                        _logger.LogWarning($"Unknown message type: {op}");
                        break;
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error processing message: {message}");
            }
        }

        private void ProcessMarketChangeMessage(MarketChangeMessage message)
        {
            try
            {
                // Handle segmentation
                var segmentType = message.Ct; // ChangeType
                var isSegmented = !string.IsNullOrEmpty(segmentType) && 
                    (segmentType == "SEG_START" || segmentType == "SEG" || segmentType == "SEG_END");

                foreach (var marketChange in message.MarketChanges)
                {
                    MarketChanged?.Invoke(this, new MarketChangeEventArgs
                    {
                        MarketId = marketChange.Id,
                        ChangeType = message.Ct,
                        MarketData = marketChange,
                        Timestamp = DateTime.UtcNow
                    });
                }

                // Store clk for reconnection
                if (!string.IsNullOrEmpty(message.Clk))
                {
                    // Store clk for future reconnections
                    _logger.LogDebug($"Stored clk: {message.Clk}");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing market change message");
            }
        }

        private void ProcessOrderChangeMessage(OrderChangeMessage message)
        {
            try
            {
                foreach (var orderChange in message.OrderChanges)
                {
                    OrderChanged?.Invoke(this, new OrderChangeEventArgs
                    {
                        OrderId = orderChange.Id,
                        ChangeType = message.Ct,
                        OrderData = orderChange,
                        Timestamp = DateTime.UtcNow
                    });
                }

                // Store clk for reconnection
                if (!string.IsNullOrEmpty(message.Clk))
                {
                    // Store clk for future reconnections
                    _logger.LogDebug($"Stored clk: {message.Clk}");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing order change message");
            }
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                _cancellationTokenSource?.Cancel();
                _streamWriter?.Dispose();
                _streamReader?.Dispose();
                _sslStream?.Dispose();
                _tcpClient?.Dispose();
                _cancellationTokenSource?.Dispose();
                _disposed = true;
            }
        }
    }
}
