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
using Microsoft.Extensions.Configuration;
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

        // Throttling for real-time odds updates (marketId -> last update time)
        private readonly Dictionary<string, DateTime> _lastOddsUpdate = new();
        private readonly TimeSpan _oddsUpdateInterval = TimeSpan.FromSeconds(5);

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
                _streamWriter = new StreamWriter(_sslStream, Encoding.UTF8) 
                { 
                    AutoFlush = true,
                    NewLine = "\r\n"  // Betfair Stream API requires CRLF line endings
                };

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

        public async Task SubscribeToMarketsAsync(List<string> eventTypeIds = null, List<string> marketTypes = null, List<string> countryCodes = null, TimeSpan? timeWindow = null)
        {
            var marketFilter = new Dictionary<string, object>();
            
            if (eventTypeIds != null && eventTypeIds.Any())
                marketFilter["eventTypeIds"] = eventTypeIds;
            
            if (marketTypes != null && marketTypes.Any())
                marketFilter["marketTypes"] = marketTypes;
            
            if (countryCodes != null && countryCodes.Any())
                marketFilter["countryCodes"] = countryCodes;
            
            // Add time window filter if specified
            if (timeWindow.HasValue)
            {
                var now = DateTime.UtcNow;
                marketFilter["marketStartTime"] = new
                {
                    from = now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    to = now.Add(timeWindow.Value).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                };
            }

            var message = new
            {
                id = ++_messageId,
                op = "marketSubscription",
                marketFilter = marketFilter,
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
            _logger.LogWarning($"Sending market subscription with filters: {json}");
            await SendMessageAsync(message);
            _logger.LogInformation($"Subscribed to markets with filters: EventTypes={string.Join(",", eventTypeIds ?? new List<string>())}, MarketTypes={string.Join(",", marketTypes ?? new List<string>())}");
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
                if (message?.MarketChanges == null) 
                {
                    return;
                }

                foreach (var marketChange in message.MarketChanges)
                {
                
                    MarketChanged?.Invoke(this, new MarketChangeEventArgs
                    {
                        MarketId = marketChange.Id,
                        ChangeType = message.Ct,
                        MarketData = marketChange.MarketDefinition,
                        Timestamp = DateTime.UtcNow
                    });

                    if (marketChange.Rc != null)
                    {
                        // Check if we have real-time odds data (using Batb and Bdatl)
                        bool hasOddsData = marketChange.Rc.Any(r => r.Batb != null || r.Bdatl != null);
                        
                        // Throttle real-time odds updates to prevent database overload
                        bool shouldUpdate = false;
                        lock (_lastOddsUpdate)
                        {
                            if (!_lastOddsUpdate.TryGetValue(marketChange.Id, out var lastUpdate) || 
                                DateTime.UtcNow - lastUpdate >= _oddsUpdateInterval)
                            {
                                _lastOddsUpdate[marketChange.Id] = DateTime.UtcNow;
                                shouldUpdate = true;
                            }
                        }
                        
                        if (shouldUpdate && hasOddsData)
                        {
                            // Store real-time odds to Greyhound MarketBook/HorseMarketBook
                            _ = Task.Run(async () => 
                            {
                                try 
                                {
                                    await StoreRealTimeOddsAsync(marketChange);
                                }
                                catch (Exception ex)
                                {
                                    _logger.LogError(ex, $"❌ Error in StoreRealTimeOddsAsync: {ex.Message}");
                                }
                            });
                        }
                        
                        foreach (var runnerChange in marketChange.Rc)
                        {
                            // Store BSP projections if available (focus on Spn only) and runner is still active
                            if (runnerChange.Spn != null && IsRunnerActive(marketChange, runnerChange.Id))
                            {
                                _ = Task.Run(() => StoreBspProjectionAsync(marketChange.Id, runnerChange));
                            }
                            // LTP storage disabled - causes database locking and not needed for betting scripts
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
            
            // Retry logic for database lock errors
            int maxRetries = 3;
            int retryDelayMs = 100;
            
            for (int attempt = 0; attempt < maxRetries; attempt++)
            {
                try
                {
                    // Only log on first attempt to reduce log spam
                    if (attempt == 0)
                    {
                        _logger.LogDebug($"🔄 Storing BSP projection for market {marketId}, runner {runnerChange.Id}: Spn={runnerChange.Spn}");
                    }
                    
                    using var connection = new SqliteConnection(_connectionString);
                    await connection.OpenAsync();
                    
                    // Increase busy timeout to 60 seconds
                    using (var timeoutCommand = connection.CreateCommand())
                    {
                        timeoutCommand.CommandText = "PRAGMA busy_timeout = 60000;";
                        await timeoutCommand.ExecuteNonQueryAsync();
                    }

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
                    
                    // Only log successes on retry attempts or if it took multiple tries
                    if (attempt > 0)
                    {
                        _logger.LogInformation($"✅ BSP stored after {attempt + 1} attempts: market {marketId}, runner {runnerChange.Id}");
                    }
                    
                    _dbSemaphore.Release();
                    return; // Success - exit
                }
                catch (SqliteException ex) when ((ex.SqliteErrorCode == 5 || ex.SqliteErrorCode == 6) && attempt < maxRetries - 1)
                {
                    // SQLite Error 5 = database locked, Error 6 = table locked
                    _logger.LogDebug($"⚠️ Database locked (attempt {attempt + 1}/{maxRetries}), retrying in {retryDelayMs}ms...");
                    await Task.Delay(retryDelayMs);
                    retryDelayMs *= 2; // Exponential backoff
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, $"❌ Error storing BSP projection for market {marketId}, runner {runnerChange.Id}: {ex.Message}");
                    _dbSemaphore.Release();
                    return; // Non-lock error - give up
                }
            }
            
            // All retries exhausted
            _logger.LogWarning($"⚠️ Failed to store BSP after {maxRetries} attempts: market {marketId}, runner {runnerChange.Id}");
            _dbSemaphore.Release();
        }

        private async Task StoreLtpDataAsync(string marketId, RunnerChange runnerChange)
        {
            try
            {
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();
                
                // Set busy timeout to 30 seconds to handle concurrent writes
                using (var timeoutCommand = connection.CreateCommand())
                {
                    timeoutCommand.CommandText = "PRAGMA busy_timeout = 30000;";
                    await timeoutCommand.ExecuteNonQueryAsync();
                }

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

        private async Task StoreRealTimeOddsAsync(MarketChange marketChange)
        {
            await _dbSemaphore.WaitAsync();
            try
            {
                var marketId = marketChange.Id;
                
                // Determine event type - first try from market definition, then look up in database
                string eventTypeId = marketChange.MarketDefinition?.EventTypeId;
                
                if (string.IsNullOrEmpty(eventTypeId))
                {
                    // Look up event type from database (check both tables)
                    using var lookupConn = new SqliteConnection(_connectionString);
                    await lookupConn.OpenAsync();
                    
                    using (var timeoutCommand = lookupConn.CreateCommand())
                    {
                        timeoutCommand.CommandText = "PRAGMA busy_timeout = 60000;";
                        await timeoutCommand.ExecuteNonQueryAsync();
                    }
                    
                    // Try greyhound table first
                    var query = "SELECT COUNT(*) FROM GreyhoundMarketBook WHERE MarketId = $MarketId LIMIT 1";
                    using (var command = new SqliteCommand(query, lookupConn))
                    {
                        command.Parameters.AddWithValue("$MarketId", marketId);
                        var count = Convert.ToInt32(await command.ExecuteScalarAsync());
                        if (count > 0)
                        {
                            eventTypeId = "4339"; // Greyhound
                        }
                    }
                    
                    // If not greyhound, try horse table
                    if (string.IsNullOrEmpty(eventTypeId))
                    {
                        query = "SELECT COUNT(*) FROM HorseMarketBook WHERE MarketId = $MarketId LIMIT 1";
                        using (var command = new SqliteCommand(query, lookupConn))
                        {
                            command.Parameters.AddWithValue("$MarketId", marketId);
                            var count = Convert.ToInt32(await command.ExecuteScalarAsync());
                            if (count > 0)
                            {
                                eventTypeId = "7"; // Horse
                            }
                        }
                    }
                }
                
                // Process both greyhound (4339) and horse (7) racing
                if (eventTypeId != "4339" && eventTypeId != "7")
                {
                    return; // Skip non-racing markets
                }
                
                string tableName = eventTypeId == "4339" ? "GreyhoundMarketBook" : "HorseMarketBook";
                string runnerNameCol = eventTypeId == "4339" ? "RunnerName" : "RUNNER_NAME";
                string boxCol = eventTypeId == "4339" ? "box" : "STALL_DRAW";
                string runnerIdCol = eventTypeId == "4339" ? "RunnerId" : "RUNNER_ID";
                
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();
                
                using (var timeoutCommand = connection.CreateCommand())
                {
                    timeoutCommand.CommandText = "PRAGMA busy_timeout = 60000;";
                    await timeoutCommand.ExecuteNonQueryAsync();
                }

                // Get existing runner metadata (names, venue, etc.) from database
                var metadataQuery = $@"
                    SELECT DISTINCT SelectionId, {runnerNameCol}, Venue, EventDate, EventName, {boxCol}, {runnerIdCol}
                    FROM {tableName}
                    WHERE MarketId = $MarketId AND {runnerNameCol} IS NOT NULL
                    LIMIT 100";
                
                var runnerMetadata = new Dictionary<long, (string name, string venue, string eventDate, string eventName, double? box, string runnerId)>();
                using (var metaCommand = new SqliteCommand(metadataQuery, connection))
                {
                    metaCommand.Parameters.AddWithValue("$MarketId", marketId);
                    using var reader = await metaCommand.ExecuteReaderAsync();
                    while (await reader.ReadAsync())
                    {
                        var selectionId = reader.GetInt64(0);
                        var runnerName = reader.IsDBNull(1) ? null : reader.GetString(1);
                        var venue = reader.IsDBNull(2) ? null : reader.GetString(2);
                        var eventDate = reader.IsDBNull(3) ? null : reader.GetString(3);
                        var eventName = reader.IsDBNull(4) ? null : reader.GetString(4);
                        var box = reader.IsDBNull(5) ? (double?)null : reader.GetDouble(5);
                        var runnerId = reader.IsDBNull(6) ? null : reader.GetString(6);
                        
                        if (runnerName != null)
                            runnerMetadata[selectionId] = (runnerName, venue, eventDate, eventName, box, runnerId);
                    }
                }

                // First, delete existing odds for this market to avoid stale data
                var deleteQuery = $"DELETE FROM {tableName} WHERE MarketId = $MarketId AND PriceType IN ('AvailableToBack', 'AvailableToLay')";
                using (var deleteCommand = new SqliteCommand(deleteQuery, connection))
                {
                    deleteCommand.Parameters.AddWithValue("$MarketId", marketId);
                    await deleteCommand.ExecuteNonQueryAsync();
                }

                // Insert fresh odds from Stream API
                var insertQuery = $@"
                    INSERT INTO {tableName} 
                    (MarketId, MarketName, SelectionId, Status, PriceType, Price, Size, {runnerNameCol}, Venue, EventDate, EventName, {boxCol}, {runnerIdCol})
                    VALUES ($MarketId, $MarketName, $SelectionId, $Status, $PriceType, $Price, $Size, $RunnerName, $Venue, $EventDate, $EventName, $box, $RunnerId)";

                int totalPricesStored = 0;
                
                foreach (var runnerChange in marketChange.Rc)
                {
                    if (!IsRunnerActive(marketChange, runnerChange.Id))
                        continue;

                    // Get runner metadata from database or fall back to market definition
                    string runnerName;
                    string venue;
                    string eventDate;
                    string eventName;
                    double? boxNumber;
                    string runnerId;
                    
                    if (runnerMetadata.TryGetValue(runnerChange.Id, out var metadata))
                    {
                        runnerName = metadata.name;
                        venue = metadata.venue;
                        eventDate = metadata.eventDate;
                        eventName = metadata.eventName;
                        boxNumber = metadata.box;
                        runnerId = metadata.runnerId;
                    }
                    else
                    {
                        // Fallback to market definition
                        var runnerDef = marketChange.MarketDefinition?.Runners?.FirstOrDefault(r => r.Id == runnerChange.Id);
                        runnerName = $"Runner {runnerChange.Id}";
                        venue = marketChange.MarketDefinition?.Venue;
                        eventDate = marketChange.MarketDefinition?.MarketTime?.ToString("yyyy-MM-dd HH:mm:ss");
                        eventName = marketChange.MarketDefinition?.Event?.Name;
                        boxNumber = runnerChange.Hc;
                        runnerId = runnerChange.Id.ToString();
                    }
                    
                    var status = "ACTIVE";

                    // Store Back prices (Batb)
                    if (runnerChange.Batb != null)
                    {
                        foreach (var priceLevel in runnerChange.Batb)
                        {
                            if (priceLevel.Count >= 2)
                            {
                                using var cmd = new SqliteCommand(insertQuery, connection);
                                cmd.Parameters.AddWithValue("$MarketId", marketId);
                                cmd.Parameters.AddWithValue("$MarketName", marketChange.MarketDefinition?.MarketType ?? "WIN");
                                cmd.Parameters.AddWithValue("$SelectionId", runnerChange.Id);
                                cmd.Parameters.AddWithValue("$Status", status);
                                cmd.Parameters.AddWithValue("$PriceType", "AvailableToBack");
                                cmd.Parameters.AddWithValue("$Price", priceLevel[0]); // Price
                                cmd.Parameters.AddWithValue("$Size", priceLevel[1]); // Size
                                cmd.Parameters.AddWithValue("$RunnerName", runnerName ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$Venue", venue ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$EventDate", eventDate ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$EventName", eventName ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$box", boxNumber ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$RunnerId", runnerId ?? (object)DBNull.Value);
                                await cmd.ExecuteNonQueryAsync();
                                totalPricesStored++;
                            }
                        }
                    }

                    // Store Lay prices (Bdatl - Best Displayed Available To Lay)
                    if (runnerChange.Bdatl != null)
                    {
                        foreach (var priceLevel in runnerChange.Bdatl)
                        {
                            if (priceLevel.Count >= 2)
                            {
                                using var cmd = new SqliteCommand(insertQuery, connection);
                                cmd.Parameters.AddWithValue("$MarketId", marketId);
                                cmd.Parameters.AddWithValue("$MarketName", marketChange.MarketDefinition?.MarketType ?? "WIN");
                                cmd.Parameters.AddWithValue("$SelectionId", runnerChange.Id);
                                cmd.Parameters.AddWithValue("$Status", status);
                                cmd.Parameters.AddWithValue("$PriceType", "AvailableToLay");
                                cmd.Parameters.AddWithValue("$Price", priceLevel[0]); // Price
                                cmd.Parameters.AddWithValue("$Size", priceLevel[1]); // Size
                                cmd.Parameters.AddWithValue("$RunnerName", runnerName ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$Venue", venue ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$EventDate", eventDate ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$EventName", eventName ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$box", boxNumber ?? (object)DBNull.Value);
                                cmd.Parameters.AddWithValue("$RunnerId", runnerId ?? (object)DBNull.Value);
                                await cmd.ExecuteNonQueryAsync();
                                totalPricesStored++;
                            }
                        }
                    }
                }

                _logger.LogInformation($"✅ Real-time odds stored for market {marketId} in {tableName} ({totalPricesStored} price points)");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"❌ Error storing real-time odds for market {marketChange.Id}: {ex.Message}");
            }
            finally
            {
                _dbSemaphore.Release();
            }
        }

        private async Task CreateStreamBspTableIfNotExistsAsync()
        {
            try
            {
                using var connection = new SqliteConnection(_connectionString);
                await connection.OpenAsync();
                
                // Set busy timeout to 30 seconds to handle concurrent writes
                using (var timeoutCommand = connection.CreateCommand())
                {
                    timeoutCommand.CommandText = "PRAGMA busy_timeout = 30000;";
                    await timeoutCommand.ExecuteNonQueryAsync();
                }

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
