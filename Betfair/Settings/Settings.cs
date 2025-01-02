namespace Betfair.Settings;
public class EndpointSettings
{
    public string ExchangeEndpoint { get; set; }
    public string AccountEndpoint { get; set; }
    public string CertLoginEndpoint { get; set; }
    public string GetMyDataEndpoint { get; set; }
    public string GetCollectionOptionsEndpoint { get; set; }
    public string GetAdvBasketDataSizeEndpoint { get; set; }
    public string DownloadListOfFilesEndpoint { get; set; }
    public string DownloadFileEndpoint { get; set; }
}

public class AuthSettings
{
    public string AppKey { get; set; }
    public string Username { get; set; }
    public string Password { get; set; }
    public string CertificatePath { get; set; }
    public string CertificatePassword { get; set; }
}


