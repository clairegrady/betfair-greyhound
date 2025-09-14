using System.Text;
using System.Text.Json;
using Betfair.Data;
using Betfair.Models;
using Betfair.Models.Data;
using Betfair.Services.Account;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services.HistoricalData;

public class HistoricalDataService : IHistoricalDataService
{
    private readonly HttpClient _httpClient;
    private readonly BetfairAuthService _authService;
    private readonly HistoricalDataDb _historicalDataDb;
    private readonly EndpointSettings _settings;
    private string _sessionToken;

    public HistoricalDataService(
        HttpClient httpClient,
        BetfairAuthService authService,
        IOptions<EndpointSettings> options,
        HistoricalDataDb historicalDataDb)
    {
        _httpClient = httpClient;
        _authService = authService;
        _settings = options.Value;
        _historicalDataDb = historicalDataDb;
    }

    public async Task<string> ListDataPackagesAsync()
    {
        _sessionToken = await _authService.GetSessionTokenAsync();

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "HistoricData/v1.0/GetMyData",
            @params = new { },
            id = 1
        };
        _httpClient.DefaultRequestHeaders.Add("ssoid", _sessionToken);
        
        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.GetMyDataEndpoint, content);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync();
    }

    public async Task<string> GetCollectionOptionsAsync(string sport, string plan, int fromDay, int fromMonth,
        int fromYear, int toDay, int toMonth, int toYear, List<string> marketTypes, List<string> countries,
        List<string> fileTypes)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "HistoricData/v1.0/GetCollectionOptions",
            @params = new
            {
                sport,
                plan,
                fromDay,
                fromMonth,
                fromYear,
                toDay,
                toMonth,
                toYear,
                eventId = "",
                eventName = "",
                marketTypesCollection = marketTypes,
                countriesCollection = countries,
                fileTypesCollection = fileTypes
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Add("ssoid", _sessionToken);
        //Console.WriteLine(_sessionToken);
        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.GetCollectionOptionsEndpoint, content);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync();
    }

    public async Task<string> GetDataSizeAsync(HistoricalDataRequest request)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "HistoricData/v1.0/GetAdvBasketDataSize",
            @params = new
            {
                request.Sport,
                request.Plan,
                request.FromDay,
                request.FromMonth,
                request.FromYear,
                request.ToDay,
                request.ToMonth,
                request.ToYear,
                marketTypesCollection = request.MarketTypes,
                countriesCollection = request.Countries
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Add("ssoid", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.GetAdvBasketDataSizeEndpoint, content);
        response.EnsureSuccessStatusCode();
        if (!response.IsSuccessStatusCode)
        {
            var errorResponse = await response.Content.ReadAsStringAsync();
            //Console.WriteLine($"Error in response: {errorResponse}");
        }
        return await response.Content.ReadAsStringAsync();
    }

    public async Task<List<string>> DownloadListOfFilesAsync(string sport, string plan, int fromDay, int fromMonth,
        int fromYear, int toDay, int toMonth, int toYear, List<string> marketTypes, List<string> countries,
        List<string> fileTypes)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();

        var requestBody = new
        {
            jsonrpc = "2.0",
            method = "HistoricData/v1.0/DownloadListOfFiles",
            @params = new
            {
                sport,
                plan,
                fromDay,
                fromMonth,
                fromYear,
                toDay,
                toMonth,
                toYear,
                marketTypesCollection = marketTypes,
                countriesCollection = countries,
                fileTypeCollection = fileTypes
            },
            id = 1
        };

        _httpClient.DefaultRequestHeaders.Add("ssoid", _sessionToken);

        var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_settings.DownloadFileEndpoint, content);
        response.EnsureSuccessStatusCode();
        var responseContent = await response.Content.ReadAsStringAsync();
        var filePaths = JsonSerializer.Deserialize<List<string>>(responseContent);
        return filePaths ?? new List<string>();
    }

    public async Task DownloadFileAsync(string filePath)
    {
        _sessionToken = await _authService.GetSessionTokenAsync();

        var fileUrl =
            $"https://historicdata.betfair.com/api/DownloadFile?filePath={Uri.EscapeDataString(filePath)}";

        var response = await _httpClient.GetAsync(fileUrl);
        if (response.IsSuccessStatusCode)
        {
            var fileName = Path.GetFileName(filePath);
            var fileStream = await response.Content.ReadAsStreamAsync();
            using (var fs = new FileStream(fileName, FileMode.Create, FileAccess.Write))
            {
                await fileStream.CopyToAsync(fs);
            }

            //Console.WriteLine($"Downloaded {fileName}");
        }
        else
        {
            //Console.WriteLine($"Failed to download {filePath}");
        }
    }

    public async Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertHistoricalDataAsync(string sport,
        string plan, int fromDay, int fromMonth, int fromYear, int toDay, int toMonth, int toYear,
        List<string> marketTypes, List<string> countries, List<string> fileTypes)
    {
        try
        {
            var responseContent = await ListDataPackagesAsync();

            var dataPackages = JsonSerializer.Deserialize<ApiResponse<HistoricalDataPackage>>(responseContent);
            if (dataPackages == null || dataPackages.Result == null || !dataPackages.Result.Any())
            {
                return (false, "No historical data available.");
            }

            var filePaths = await DownloadListOfFilesAsync(sport, plan, fromDay, fromMonth, fromYear, toDay,
                toMonth, toYear, marketTypes, countries, fileTypes);

            foreach (var filePath in filePaths)
            {
                await DownloadFileAsync(filePath);
            }

            return (true, string.Empty);
        }
        catch (Exception ex)
        {
            return (false, $"Internal error: {ex.Message}");
        }
    }
}

public interface IHistoricalDataService
{
    Task<string> ListDataPackagesAsync();

    Task<string> GetCollectionOptionsAsync(
        string sport,
        string plan,
        int fromDay,
        int fromMonth,
        int fromYear,
        int toDay,
        int toMonth,
        int toYear,
        List<string> marketTypes,
        List<string> countries,
        List<string> fileTypes);

    Task<string> GetDataSizeAsync(HistoricalDataRequest request);

    Task<List<string>> DownloadListOfFilesAsync(
        string sport,
        string plan,
        int fromDay,
        int fromMonth,
        int fromYear,
        int toDay,
        int toMonth,
        int toYear,
        List<string> marketTypes,
        List<string> countries,
        List<string> fileTypes);

    Task DownloadFileAsync(string filePath);
    Task<(bool IsSuccess, string ErrorMessage)> FetchAndInsertHistoricalDataAsync(
        string sport,
        string plan,
        int fromDay,
        int fromMonth,
        int fromYear,
        int toDay,
        int toMonth,
        int toYear,
        List<string> marketTypes,
        List<string> countries,
        List<string> fileTypes);
}

public class CollectionOptionResponse
{
    public List<MarketType> marketTypesCollection { get; set; }
    public List<Country> countriesCollection { get; set; }
    public List<FileType> fileTypesCollection { get; set; }
}

public class MarketType
{
    public string name { get; set; }
    public int count { get; set; }
}

public class Country
{
    public string name { get; set; }
    public int count { get; set; }
}

public class FileType
{
    public string name { get; set; }
    public int count { get; set; }
}

