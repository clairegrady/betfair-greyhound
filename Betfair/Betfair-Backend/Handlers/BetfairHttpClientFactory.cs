using System.Net.Http.Headers;
using System.Security.Cryptography.X509Certificates;
using Betfair.Settings;
using Microsoft.Extensions.Options;

namespace Betfair.Handlers;
public class BetfairHttpClientFactory
{
    public static void ConfigureBetfairClient(HttpClient client, IServiceProvider sp)
    {
        var options = sp.GetRequiredService<IOptions<AuthSettings>>().Value;
        client.DefaultRequestHeaders.Add("X-Application", options.AppKey);
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public static HttpClientHandler CreateBetfairHandler(IServiceProvider sp)
    {
        var options = sp.GetRequiredService<IOptions<AuthSettings>>().Value;
        return new HttpClientHandler
        {
            ClientCertificates = { new X509Certificate2(options.CertificatePath, options.CertificatePassword) }
        };
    }
}