using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using System.Text.Json.Serialization;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Services.Account;

public class LoginResponse
{
    [JsonPropertyName("sessionToken")]
    public string SessionToken { get; set; }

    [JsonPropertyName("loginStatus")]
    public string LoginStatus { get; set; }
}

public class BetfairAuthService
{
    private readonly HttpClient _httpClient;
    private readonly string _appKey;
    private readonly string _username;
    private readonly string _password;
    private string _sessionToken; 
    private DateTime _sessionTokenExpiry = DateTime.MinValue;
    private readonly EndpointSettings _settings;
    

    public BetfairAuthService(IOptions<AuthSettings> options, IOptions<EndpointSettings> settings)
    {
        var handler = new HttpClientHandler();
        var certificate = new X509Certificate2(options.Value.CertificatePath, options.Value.CertificatePassword);

        handler.ClientCertificates.Add(certificate);

        _httpClient = new HttpClient(handler);
        _appKey = options.Value.AppKey;
        _username = options.Value.Username;
        _password = options.Value.Password;
        _settings = settings.Value;
    }

    public string AppKey => _appKey;

    public async Task<string> GetSessionTokenAsync()
    {
        // Always get fresh token if expired or within 5 minutes of expiry
        if (string.IsNullOrEmpty(_sessionToken) || DateTime.UtcNow >= _sessionTokenExpiry.AddMinutes(-5))
        {
            _sessionToken = await AuthenticateAsync();
            // Betfair session tokens typically last 8 hours
            _sessionTokenExpiry = DateTime.UtcNow.AddHours(8);
        }
        return _sessionToken;
    }
    
    public async Task<string> GetFreshSessionTokenAsync()
    {
        // Force a new authentication for Stream API
        _sessionToken = await AuthenticateAsync();
        _sessionTokenExpiry = DateTime.UtcNow.AddHours(8);
        return _sessionToken;
    }

    public async Task<string> AuthenticateAsync()
    {
        var requestUri = _settings.CertLoginEndpoint;
        var requestMessage = new HttpRequestMessage(HttpMethod.Post, requestUri);
        requestMessage.Headers.Add("X-Application", _appKey);
        var content = GetLoginBodyAsContent(_username, _password);
        requestMessage.Content = content;

        var response = await _httpClient.SendAsync(requestMessage);
        response.EnsureSuccessStatusCode();

        var responseContent = await response.Content.ReadAsStringAsync();
        var loginResponse = JsonSerializer.Deserialize<LoginResponse>(responseContent);

        if (loginResponse != null && !string.IsNullOrEmpty(loginResponse.SessionToken))
        {
            return loginResponse.SessionToken;
        }
        throw new Exception("Failed to authenticate and retrieve session token.");
    }

    private FormUrlEncodedContent GetLoginBodyAsContent(string username, string password)
    {
        var postData = new List<KeyValuePair<string, string>>
        {
            new("username", username),
            new("password", password)
        };
        return new FormUrlEncodedContent(postData);
    }
}