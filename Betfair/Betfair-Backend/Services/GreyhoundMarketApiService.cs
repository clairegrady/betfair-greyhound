using Betfair.Services;
using System.Text.Json;
using Betfair.Models;
using Betfair.Models.Market;
using Betfair.Models.Runner;
using Betfair.Settings;
using Betfair.Services.Account;
using Microsoft.Extensions.Options;
using System.Text;
using System.Net.Http.Headers;

namespace Betfair.Services;

public class GreyhoundMarketApiService : IMarketApiService
{
    private readonly IMarketApiService _baseMarketApiService;
    private readonly ILogger<GreyhoundMarketApiService> _logger;
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly EndpointSettings _settings;

    public GreyhoundMarketApiService(
        IMarketApiService baseMarketApiService, 
        ILogger<GreyhoundMarketApiService> logger,
        HttpClient httpClient,
        BetfairAuthService authService,
        IOptions<EndpointSettings> settings)
    {
        _baseMarketApiService = baseMarketApiService;
        _logger = logger;
        _httpClient = httpClient;
        _authService = authService;
        _settings = settings.Value;
    }

    public async Task<string> ListMarketBookAsync(List<string> marketIds)
    {
        try
        {
            _logger.LogInformation("Fetching greyhound market books for {Count} markets", marketIds.Count);
            return await _baseMarketApiService.ListMarketBookAsync(marketIds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching greyhound market books");
            throw;
        }
    }

    public async Task<string> ListMarketCatalogue(string? competitionId = null, string? eventId = null)
    {
        try
        {
            // Use greyhound event type ID (4339) - this is the correct signature for the interface
            _logger.LogInformation("Fetching greyhound market catalogue for competition {CompetitionId}, event {EventId}", competitionId, eventId);
            
            // For greyhounds, we need to implement this differently since the base service is for horse racing
            return await GetGreyhoundMarketCatalogueJson(competitionId, eventId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching greyhound market catalogue");
            throw;
        }
    }

    private async Task<string> GetGreyhoundMarketCatalogueJson(string? competitionId = null, string? eventId = null)
    {
        try
        {
            var sessionToken = await _authService.GetSessionTokenAsync();
            if (string.IsNullOrEmpty(sessionToken))
            {
                _logger.LogError("Failed to get session token for greyhound markets");
                return "{\"result\":[]}";
            }

            var filter = new
            {
                competitionIds = competitionId != null ? new[] { competitionId } : null,
                eventIds = eventId != null ? new[] { eventId } : null,
                // Only filter by event type if we don't have a specific event ID
                eventTypeIds = eventId == null ? new List<string> { "4339" } : null, // Greyhound Event Type ID
                marketTypeCodes = new[] { "WIN", "PLACE" },
                marketStatuses = new[] { "OPEN", "ACTIVE", "SUSPENDED" },
                marketCountries = new[] { "AU", "NZ" } // Australian and New Zealand greyhounds
            };

            var requestBody = new
            {
                jsonrpc = "2.0",
                method = "SportsAPING/v1.0/listMarketCatalogue",
                @params = new
                {
                    filter = filter,
                    maxResults = 100,
                    marketProjection = new[] { "COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA" }
                },
                id = 1
            };

            _httpClient.DefaultRequestHeaders.Clear();
            _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            _httpClient.DefaultRequestHeaders.Add("X-Application", _authService.AppKey);
            _httpClient.DefaultRequestHeaders.Add("X-Authentication", sessionToken);

            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(_settings.ExchangeEndpoint, content);
            response.EnsureSuccessStatusCode();

            var jsonResponse = await response.Content.ReadAsStringAsync();
            _logger.LogInformation("Successfully fetched greyhound market catalogue from Betfair API. Response length: {Length}", jsonResponse.Length);
            _logger.LogDebug("Greyhound market catalogue response: {Response}", jsonResponse);
            
            // Add console output for debugging
            Console.WriteLine($"🔍 GreyhoundMarketApiService API Response Length: {jsonResponse.Length}");
            Console.WriteLine($"📥 API Response: {jsonResponse}");
            
            return jsonResponse;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching greyhound market catalogue from Betfair API");
            return "{\"result\":[]}";
        }
    }

    public async Task<string> GetMarketProfitAndLossAsync(List<string> marketIds)
    {
        try
        {
            _logger.LogInformation("Fetching greyhound market profit and loss for {Count} markets", marketIds.Count);
            return await _baseMarketApiService.GetMarketProfitAndLossAsync(marketIds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching greyhound market profit and loss");
            throw;
        }
    }

    public async Task ProcessAndStoreMarketProfitAndLoss(List<string> marketIds)
    {
        try
        {
            _logger.LogInformation("Processing and storing greyhound market profit and loss for {Count} markets", marketIds.Count);
            await _baseMarketApiService.ProcessAndStoreMarketProfitAndLoss(marketIds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing and storing greyhound market profit and loss");
            throw;
        }
    }

    public async Task<string> ListHorseRacingMarketCatalogueAsync(string? eventTypeId = null, string? eventId = null, DateTime? openDate = null)
    {
        // This method is not applicable for greyhounds, but we'll redirect to the general method
        return await ListMarketCatalogue(eventId: eventId);
    }

    public async Task<string> ListBasketballMarketCatalogueAsync(string? competitionId = null, string? eventId = null)
    {
        // This method is not applicable for greyhounds - delegate to base service
        _logger.LogInformation("Basketball market catalogue requested via GreyhoundMarketApiService - delegating to base service");
        return await _baseMarketApiService.ListBasketballMarketCatalogueAsync(competitionId, eventId);
    }

    public async Task<List<string>> GetUnprocessedMarketIds(List<string> allMarketIds)
    {
        try
        {
            _logger.LogInformation("Getting unprocessed greyhound market IDs from {Count} total markets", allMarketIds.Count);
            return await _baseMarketApiService.GetUnprocessedMarketIds(allMarketIds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting unprocessed greyhound market IDs");
            throw;
        }
    }

    public async Task<List<MarketCatalogue>> GetGreyhoundMarketCataloguesAsync(string? eventId = null, string? competitionId = null)
    {
        try
        {
            var marketCatalogueJson = await ListMarketCatalogue(competitionId, eventId);
            var marketCatalogueApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketCatalogue>>(marketCatalogueJson);

            if (marketCatalogueApiResponse?.Result == null || !marketCatalogueApiResponse.Result.Any())
            {
                _logger.LogWarning("No greyhound market catalogues found");
                return new List<MarketCatalogue>();
            }

            var marketCatalogues = marketCatalogueApiResponse.Result
                .Where(catalogue => catalogue.Event != null)
                .Select(catalogue => new MarketCatalogue
                {
                    MarketId = catalogue.MarketId,
                    MarketName = catalogue.MarketName,
                    TotalMatched = catalogue.TotalMatched,
                    EventType = catalogue.EventType,
                    Competition = catalogue.Competition,
                    Event = catalogue.Event,
                    Runners = catalogue.Runners
                })
                .Where(catalogue => catalogue.Event != null)
                .ToList();

            _logger.LogInformation("Found {Count} greyhound market catalogues", marketCatalogues.Count);
            return marketCatalogues;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting greyhound market catalogues");
            return new List<MarketCatalogue>();
        }
    }

    public async Task<List<MarketBook<ApiRunner>>> ProcessGreyhoundMarketBooksAsync(List<string> marketIds)
    {
        try
        {
            var marketBookJson = await ListMarketBookAsync(marketIds);
            var marketBookApiResponse = JsonSerializer.Deserialize<ApiResponse<MarketBook<ApiRunner>>>(marketBookJson);

            if (marketBookApiResponse?.Result?.Any() == true)
            {
                var marketBooks = marketBookApiResponse.Result
                    .Where(book => book.MarketId != null)
                    .Select(book => new MarketBook<ApiRunner>
                    {
                        MarketId = book.MarketId,
                        Status = book.Status,
                        BetDelay = book.BetDelay,
                        LastMatchTime = book.LastMatchTime,
                        TotalMatched = book.TotalMatched,
                        Runners = book.Runners?.Select(runner => new ApiRunner
                        {
                            SelectionId = runner.SelectionId,
                            Status = runner.Status,
                            LastPriceTraded = runner.LastPriceTraded,
                            TotalMatched = runner.TotalMatched,
                            Exchange = runner.Exchange != null
                                ? new Exchange
                                {
                                    AvailableToBack = runner.Exchange.AvailableToBack?.Select(p => new PriceSize
                                    {
                                        Price = p.Price,
                                        Size = p.Size
                                    }).ToList() ?? new List<PriceSize>(),

                                    AvailableToLay = runner.Exchange.AvailableToLay?.Select(p => new PriceSize
                                    {
                                        Price = p.Price,
                                        Size = p.Size
                                    }).ToList() ?? new List<PriceSize>(),

                                    TradedVolume = runner.Exchange.TradedVolume?.Select(p => new PriceSize
                                    {
                                        Price = p.Price,
                                        Size = p.Size
                                    }).ToList() ?? new List<PriceSize>()
                                }
                                : null,
                        }).ToList() ?? new List<ApiRunner>()
                    })
                    .ToList();

                _logger.LogInformation("Processed {Count} greyhound market books", marketBooks.Count);
                return marketBooks;
            }

            _logger.LogWarning("No greyhound market books found in API response");
            return new List<MarketBook<ApiRunner>>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing greyhound market books");
            return new List<MarketBook<ApiRunner>>();
        }
    }
}
