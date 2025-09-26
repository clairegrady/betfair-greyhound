using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Security;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Data.Sqlite;
using Betfair.Models;
using Betfair.Settings;

namespace Betfair.Services
{
    public class StreamApiService : IStreamApiService, IDisposable
    {
        private readonly ILogger<StreamApiService> _logger;
        private readonly StreamApiSettings _settings;
        private readonly string _connectionString;
        private readonly SemaphoreSlim _dbSemaphore = new SemaphoreSlim(1, 1);

        private TcpClient _tcpClient;
        private SslStream _sslStream;
        private StreamReader _streamReader;
        private StreamWriter _streamWriter;
        private CancellationTokenSource _cancellationTokenSource;

        private int _messageId = 0;
        private bool _connectionReceived = false;
        private bool _authenticated = false;
        private readonly SemaphoreSlim _connectionSemaphore = new(0, 1);

        private string _pendingAppKey;
        private string _pendingSessionToken;
        private readonly Dictionary<int, object> _pendingMessages = new();

        public bool IsConnected => _tcpClient?.Connected == true && _sslStream?.IsAuthenticated == true;
        public bool IsAuthenticated => _authenticated;

        public event EventHandler<MarketChangeEventArgs> MarketChanged;
        public event EventHandler<OrderChangeEventArgs> OrderChanged;
        public event EventHandler<StatusEventArgs> StatusReceived;

        public StreamApiService(ILogger<StreamApiService> logger, IOptions<StreamApiSettings> settings,
            IConfiguration configuration)
        {
            _logger = logger;
            _settings = settings.Value;
            _connectionString = configuration.GetConnectionString("DefaultDb");

            // Ensure StreamBspProjections table exists
            _ = Task.Run(CreateStreamBspTableIfNotExistsAsync);
        }

        public async Task<bool> ConnectAsync()
        {
            try
            {
                _cancellationTokenSource = new CancellationTokenSource();

                var host = _settings.UseIntegration ? "stream-api-integration.betfair.com" : "stream-api.betfair.com";
                var port = 443;

                _tcpClient = new TcpClient();
                await _tcpClient.ConnectAsync(host, port);

                _sslStream = new SslStream(_tcpClient.GetStream(), false);
                await _sslStream.AuthenticateAsClientAsync(host);

                _streamReader = new StreamReader(_sslStream, Encoding.UTF8);
                _streamWriter = new StreamWriter(_sslStream, Encoding.UTF8) { AutoFlush = true };

                _ = Task.Run(ReceiveMessagesAsync);

                _logger.LogInformation("Connected to Betfair Stream API");
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to connect to Stream API");
                return false;
            }
        }

        public async Task<bool> AuthenticateAsync(string appKey, string sessionToken)
        {
            _pendingAppKey = appKey;
            _pendingSessionToken = sessionToken;

            if (!_connectionReceived)
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                await _connectionSemaphore.WaitAsync(cts.Token);
            }

            if (!string.IsNullOrEmpty(_pendingAppKey) && !string.IsNullOrEmpty(_pendingSessionToken))
            {
                await SendAuthenticationMessage(_pendingAppKey, _pendingSessionToken);
            }

            return _authenticated;
        }

        public async Task SubscribeToMarketAsync(string marketId, string[] marketFilter = null)
        {
            var message = new
            {
                id = ++_messageId,
                op = "marketSubscription",
                marketFilter = new
                {
                    marketIds = new[] { marketId },
                    bspMarket = true,
                    turnInPlayEnabled = true
                },
                marketDataFilter = new
                {
                    fields = new[]
                    {
                        "SP_PROJECTED", // BSP Near and Far prices
                        "EX_BEST_OFFERS_DISP",
                        "EX_BEST_OFFERS",
                        "EX_MARKET_DEF",
                        "EX_LTP" // Last Traded Price
                    },
                    ladderLevels = 3
                },
                segmentationEnabled = true,
                conflateMs = 0,
                heartbeatMs = 5000
            };

            var json = JsonSerializer.Serialize(message);
            _logger.LogWarning($"Sending market subscription: {json}");
            await SendMessageAsync(message);
            _logger.LogInformation($"Subscribed to market {marketId} with BSP projections");
        }

        public async Task SubscribeToOrdersAsync()
        {
            var message = new
            {
                id = ++_messageId,
                op = "orderSubscription",
                conflateMs = 0,
                heartbeatMs = 5000
            };

            await SendMessageAsync(message);
            _logger.LogInformation("Subscribed to order changes");
        }

        public async Task UnsubscribeFromMarketAsync(string marketId)
        {
            _logger.LogInformation($"Unsubscribed from market {marketId}");
            await Task.CompletedTask;
        }

        public async Task SendHeartbeatAsync()
        {
            var message = new { id = ++_messageId, op = "heartbeat" };
            await SendMessageAsync(message);
            _logger.LogInformation("Heartbeat sent");
        }

        private async Task SendAuthenticationMessage(string appKey, string sessionToken)
        {
            try
            {
                _logger.LogInformation("=== SENDING IMMEDIATE AUTHENTICATION ===");

                var authMessage = new AuthenticationMessage
                {
                    Id = ++_messageId,
                    Op = "authentication",
                    AppKey = appKey,
                    Session = sessionToken
                };

                var json = JsonSerializer.Serialize(authMessage);
                await _streamWriter.WriteLineAsync(json);
                await _streamWriter.FlushAsync();

                _logger.LogInformation($"Authentication message sent: Id={authMessage.Id}");

                // Wait for response (timeout 10s)
                var tcs = new TaskCompletionSource<AuthenticationResponse>();
                _pendingMessages[authMessage.Id] = tcs;

                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
                cts.Token.Register(() => tcs.TrySetCanceled());

                AuthenticationResponse response = null;
                try
                {
                    response = await tcs.Task;
                }
                catch (TaskCanceledException)
                {
                    _logger.LogError("Authentication response timed out");
                    _authenticated = false;
                    return;
                }

                if (response != null && response.StatusCode == "SUCCESS")
                {
                    _authenticated = true;
                    _logger.LogInformation("✅ Authentication successful");
                }
                else
                {
                    _authenticated = false;
                    _logger.LogError(
                        $"❌ Authentication failed: StatusCode={response?.StatusCode}, ErrorCode={response?.ErrorCode}, ErrorMessage={response?.ErrorMessage}");
                }
            }
            catch (Exception ex)
            {
                _authenticated = false;
                _logger.LogError(ex, "Error in immediate authentication");
            }
        }

        private async Task ReceiveMessagesAsync()
        {
            try
            {
                while (IsConnected && !_cancellationTokenSource.IsCancellationRequested)
                {
                    var line = await _streamReader.ReadLineAsync();
                    if (string.IsNullOrWhiteSpace(line)) continue;

                    await ProcessMessageAsync(line);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error receiving messages from Stream API");
            }
        }

        private async Task ProcessMessageAsync(string message)
        {
            try
            {
                _logger.LogWarning($"Received message from Betfair: {message}");
                using var jsonDoc = JsonDocument.Parse(message);
                var root = jsonDoc.RootElement;
                var op = root.GetProperty("op").GetString();
                int? id = root.TryGetProperty("id", out var idElement) ? idElement.GetInt32() : null;

                switch (op)
                {
                    case "connection":
                        var connectionMsg = JsonSerializer.Deserialize<ConnectionMessage>(message);
                        _logger.LogInformation($"Connection established: {connectionMsg.ConnectionId}");
                        _connectionReceived = true;
                        _connectionSemaphore.Release();

                        if (!string.IsNullOrEmpty(_pendingAppKey) && !string.IsNullOrEmpty(_pendingSessionToken))
                            await SendAuthenticationMessage(_pendingAppKey, _pendingSessionToken);
                        break;

                    case "status":
                        var statusMsg = JsonSerializer.Deserialize<AuthenticationResponse>(message);
                        StatusReceived?.Invoke(this, new StatusEventArgs
                        {
                            StatusCode = statusMsg.StatusCode,
                            ErrorCode = statusMsg.ErrorCode,
                            ErrorMessage = statusMsg.ErrorMessage
                        });

                        if (id.HasValue && _pendingMessages.TryGetValue(id.Value, out var tcsObj))
                        {
                            if (tcsObj is TaskCompletionSource<AuthenticationResponse> authTcs)
                                authTcs.SetResult(statusMsg);
                            _pendingMessages.Remove(id.Value);
                        }

                        break;

                    case "mcm": // Market Change Message
                        _logger.LogWarning($"Processing Market Change Message: {message}");
                        var marketChangeMsg = JsonSerializer.Deserialize<MarketChangeMessage>(message);
                        ProcessMarketChangeMessage(marketChangeMsg);
                        break;

                    case "ocm": // Order Change Message
                        var orderChangeMsg = JsonSerializer.Deserialize<OrderChangeMessage>(message);
                        ProcessOrderChangeMessage(orderChangeMsg);
                        break;

                    case "heartbeat":
                        _logger.LogDebug("Heartbeat received");
                        break;

                    default:
                        _logger.LogWarning($"Unknown message type: {op}");
                        break;
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Failed to process message: {message}");
            }
        }

        private void ProcessMarketChangeMessage(MarketChangeMessage message)
        {
            try
            {
                _logger.LogWarning($"Processing Market Change Message: {JsonSerializer.Serialize(message)}");
                if (message?.MarketChanges == null) 
                {
                    _logger.LogWarning("MarketChanges is null, returning early");
                    return;
                }
                
                _logger.LogWarning($"Found {message.MarketChanges.Count} market changes");

                foreach (var marketChange in message.MarketChanges)
                {
                    _logger.LogWarning($"Processing market {marketChange.Id} with {marketChange.Rc?.Count ?? 0} runner changes");
                
                    MarketChanged?.Invoke(this, new MarketChangeEventArgs
                    {
                        MarketId = marketChange.Id,
                        ChangeType = message.Ct,
                        MarketData = marketChange.MarketDefinition,
                        Timestamp = DateTime.UtcNow
                    });

                    if (marketChange.Rc != null)
                    {
                        _logger.LogWarning($"Processing {marketChange.Rc.Count} runner changes for market {marketChange.Id}");
                        foreach (var runnerChange in marketChange.Rc)
                        {
                            _logger.LogWarning($"Runner {runnerChange.Id}: Spn={runnerChange.Spn}, Spf={runnerChange.Spf}, Ltp={runnerChange.Ltp}");
                            // Store BSP projections if available (focus on Spn only) and runner is still active
                            if (runnerChange.Spn != null && IsRunnerActive(marketChange, runnerChange.Id))
                            {
                                _logger.LogWarning($"BSP data found for runner {runnerChange.Id}: Spn={runnerChange.Spn}");
                                _ = Task.Run(() => StoreBspProjectionAsync(marketChange.Id, runnerChange));
                            }
                            else if (runnerChange.Spn != null)
                            {
                                _logger.LogWarning($"Skipping BSP data for scratched/removed runner {runnerChange.Id}: Spn={runnerChange.Spn}");
                            }
                            // Store LTP data if available
                            if (runnerChange.Ltp != null)
                            {
                                _logger.LogWarning($"LTP data found for runner {runnerChange.Id}: Ltp={runnerChange.Ltp}");
                                _ = Task.Run(() => StoreLtpDataAsync(marketChange.Id, runnerChange));
                            }
                        }
                    }
                }

                // Optional: store the clk for reconnections
                if (!string.IsNullOrEmpty(message.Clk))
                    _logger.LogDebug($"Stored clk for reconnection: {message.Clk}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing market change message");
            }
        }

        private async Task SendMessageAsync(object message)
        {
            if (_streamWriter == null)
                throw new InvalidOperationException("StreamWriter not initialized.");

            var json = JsonSerializer.Serialize(message);
            await _streamWriter.WriteLineAsync(json);
            await _streamWriter.FlushAsync();
        }


        private void ProcessOrderChangeMessage(OrderChangeMessage message)
        {
            if (message?.OrderChanges == null) return;

            foreach (var orderChange in message.OrderChanges)
            {
                OrderChanged?.Invoke(this, new OrderChangeEventArgs
                {
                    OrderId = orderChange.Id,
                    FullImage = orderChange.FullImage,
                    Orders = orderChange.Oc ?? new List<Order>()
                });

                // Optional: handle cancelled/replaced orders
                if (orderChange.Or != null)
                {
                    foreach (var cancelledOrder in orderChange.Or)
                    {
                        // handle cancelled orders
                    }
                }
            }
        }

        public async Task DisconnectAsync()
        {
            _cancellationTokenSource?.Cancel();
            _streamWriter?.Dispose();
            _streamReader?.Dispose();
            _sslStream?.Dispose();
            _tcpClient?.Dispose();
            await Task.CompletedTask;
        }

        public void Dispose()
        {
            DisconnectAsync().GetAwaiter().GetResult();
        }

        private bool IsRunnerActive(MarketChange marketChange, long runnerId)
        {
            if (marketChange.MarketDefinition?.Runners == null)
            {
                _logger.LogWarning($"No market definition runners found for runner {runnerId}, assuming active");
                return true; // If no market definition, assume active
            }
            
            var runner = marketChange.MarketDefinition.Runners.FirstOrDefault(r => r.Id == runnerId);
            if (runner == null)
            {
                _logger.LogWarning($"Runner {runnerId} not found in market definition, assuming active");
                return true; // If runner not found in definition, assume active
            }
            
            _logger.LogWarning($"Runner {runnerId} status: {runner.Status}");
            return runner.Status == "ACTIVE";
        }

        private async Task StoreBspProjectionAsync(string marketId, RunnerChange runnerChange)
        {
            await _dbSemaphore.WaitAsync();
            try
            {
                _logger.LogWarning($"🔄 Storing BSP projection for market {marketId}, runner {runnerChange.Id}: Spn={runnerChange.Spn}, Spf={runnerChange.Spf}");
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();

                var nearPrice = runnerChange.Spn;
                var farPrice = (object)DBNull.Value; // Not using Spf anymore
                var average = nearPrice; // Use Spn as the average BSP

                var insertQuery = @"
                INSERT OR REPLACE INTO StreamBspProjections
                (MarketId, SelectionId, RunnerName, NearPrice, FarPrice, Average, UpdatedAt)
                VALUES
                ($MarketId, $SelectionId, $RunnerName, $NearPrice, $FarPrice, $Average, $UpdatedAt)";

                using var command = new SqliteCommand(insertQuery, connection);
                command.Parameters.AddWithValue("$MarketId", marketId);
                command.Parameters.AddWithValue("$SelectionId", runnerChange.Id);
                command.Parameters.AddWithValue("$RunnerName", $"Runner {runnerChange.Id}");
                command.Parameters.AddWithValue("$NearPrice", nearPrice ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$FarPrice", farPrice ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$Average", average);
                command.Parameters.AddWithValue("$UpdatedAt", DateTime.UtcNow);

                var rowsAffected = await command.ExecuteNonQueryAsync();
                _logger.LogWarning($"✅ Successfully stored BSP projection for market {marketId}, runner {runnerChange.Id}: Near={nearPrice}, Far={farPrice}, Avg={average} (Rows affected: {rowsAffected})");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"❌ Error storing BSP projection for market {marketId}, runner {runnerChange.Id}: {ex.Message}");
            }
            finally
            {
                _dbSemaphore.Release();
            }
        }

        private async Task StoreLtpDataAsync(string marketId, RunnerChange runnerChange)
        {
            try
            {
                _logger.LogWarning($"🔄 Storing LTP data for market {marketId}, runner {runnerChange.Id}: Ltp={runnerChange.Ltp}");
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();

                var insertQuery = @"
                INSERT OR REPLACE INTO StreamLtpData
                (MarketId, SelectionId, RunnerName, LastTradedPrice, UpdatedAt)
                VALUES
                ($MarketId, $SelectionId, $RunnerName, $LastTradedPrice, $UpdatedAt)";

                using var command = new SqliteCommand(insertQuery, connection);
                command.Parameters.AddWithValue("$MarketId", marketId);
                command.Parameters.AddWithValue("$SelectionId", runnerChange.Id);
                command.Parameters.AddWithValue("$RunnerName", $"Runner {runnerChange.Id}");
                command.Parameters.AddWithValue("$LastTradedPrice", runnerChange.Ltp ?? (object)DBNull.Value);
                command.Parameters.AddWithValue("$UpdatedAt", DateTime.UtcNow);

                var rowsAffected = await command.ExecuteNonQueryAsync();
                _logger.LogWarning($"✅ Successfully stored LTP data for market {marketId}, runner {runnerChange.Id}: Ltp={runnerChange.Ltp} (Rows affected: {rowsAffected})");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"❌ Error storing LTP data for market {marketId}, runner {runnerChange.Id}: {ex.Message}");
            }
        }

        private async Task CreateStreamBspTableIfNotExistsAsync()
        {
            try
            {
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();

                var createTableQuery = @"
                CREATE TABLE IF NOT EXISTS StreamBspProjections (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    MarketId TEXT NOT NULL,
                    SelectionId INTEGER NOT NULL,
                    RunnerName TEXT,
                    NearPrice REAL,
                    FarPrice REAL,
                    Average REAL,
                    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(MarketId, SelectionId)
                )";

                using var command = new SqliteCommand(createTableQuery, connection);
                await command.ExecuteNonQueryAsync();

                // Create indexes
                var createIndexQuery1 =
                    "CREATE INDEX IF NOT EXISTS idx_streambsp_marketid ON StreamBspProjections(MarketId)";
                using var indexCommand1 = new SqliteCommand(createIndexQuery1, connection);
                await indexCommand1.ExecuteNonQueryAsync();

                var createIndexQuery2 =
                    "CREATE INDEX IF NOT EXISTS idx_streambsp_selectionid ON StreamBspProjections(SelectionId)";
                using var indexCommand2 = new SqliteCommand(createIndexQuery2, connection);
                await indexCommand2.ExecuteNonQueryAsync();

                _logger.LogInformation("StreamBspProjections table created/verified successfully");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating StreamBspProjections table");
            }
        }
    }

    public class AuthenticationResponse
    {
        [JsonPropertyName("op")] public string Op { get; set; }

        [JsonPropertyName("statusCode")] public string StatusCode { get; set; }

        [JsonPropertyName("errorCode")] public string ErrorCode { get; set; }

        [JsonPropertyName("errorMessage")] public string ErrorMessage { get; set; }
    }
}
