using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Betfair.Settings;
using Newtonsoft.Json;

namespace Betfair.Services
{
    public class StreamApiAuthService
    {
        private readonly ILogger<StreamApiAuthService> _logger;
        private readonly AuthSettings _authSettings;
        private AppKeyAndSession _session;

        public StreamApiAuthService(ILogger<StreamApiAuthService> logger, IOptions<AuthSettings> authSettings)
        {
            _logger = logger;
            _authSettings = authSettings.Value;
        }

        public async Task<AppKeyAndSession> GetOrCreateNewSessionAsync()
        {
            if (_session != null)
            {
                // Check if session is still valid (3 hours default - matches official sample)
                if ((_session.CreateTime + TimeSpan.FromHours(3)) > DateTime.UtcNow)
                {
                    _logger.LogInformation("Stream API - session not expired - re-using");
                    return _session;
                }
                else
                {
                    _logger.LogInformation("Stream API - session expired");
                }
            }

            _logger.LogInformation("Stream API - creating new session");
            
            try
            {
                // Use the exact same authentication as the official Betfair sample
                using var httpClient = new HttpClient();
                httpClient.DefaultRequestHeaders.Add("X-Application", _authSettings.AppKey);
                httpClient.DefaultRequestHeaders.Add("Accept", "application/json");

                // Use the exact URL format from the official sample
                string uri = $"https://identitysso.betfair.com/api/login?username={_authSettings.Username}&password={_authSettings.Password}";
                
                var response = await httpClient.PostAsync(uri, null);
                var responseContent = await response.Content.ReadAsStringAsync();
                
                _logger.LogInformation($"Stream API Auth Response: {responseContent}");
                
                var sessionDetails = JsonConvert.DeserializeObject<SessionDetails>(responseContent);
                
                if (sessionDetails != null && "SUCCESS".Equals(sessionDetails.status))
                {
                    _session = new AppKeyAndSession(_authSettings.AppKey, sessionDetails.token);
                    _logger.LogInformation($"Stream API authentication successful - Token: {sessionDetails.token?.Substring(0, Math.Min(10, sessionDetails.token?.Length ?? 0))}...");
                    return _session;
                }
                else
                {
                    _logger.LogError($"Stream API authentication failed - Status: {sessionDetails?.status}, Error: {sessionDetails?.error}");
                    throw new Exception($"Stream API authentication failed: {sessionDetails?.error}");
                }
            }
            catch (Exception e)
            {
                _logger.LogError(e, "Stream API authentication call failed");
                throw;
            }
        }

        public void ExpireTokenNow()
        {
            _logger.LogInformation("Stream API - expiring session token now");
            _session = null;
        }
    }

    public class AppKeyAndSession
    {
        public AppKeyAndSession(string appKey, string session)
        {
            AppKey = appKey;
            Session = session;
            CreateTime = DateTime.UtcNow;
        }

        public string AppKey { get; private set; }
        public DateTime CreateTime { get; private set; }
        public string Session { get; private set; }
    }

    public class SessionDetails
    {
        public string token;
        public string product;
        public string status;
        public string error;
    }
}
