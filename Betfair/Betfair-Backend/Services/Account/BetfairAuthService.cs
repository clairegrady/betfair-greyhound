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

    public async Task<string> GetSessionTokenAsync()
    {
        if (string.IsNullOrEmpty(_sessionToken))
        {
            _sessionToken = await AuthenticateAsync();
        }
        return _sessionToken;
    }
    
    private async Task<string> AuthenticateAsync()
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