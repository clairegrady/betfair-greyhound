using Betfair.Data;
using Betfair.Services;
using Betfair.AutomationServices;
using Betfair.AutomatedServices;
using Betfair.Services;
using Betfair.Handlers;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Betfair.Settings;
using Microsoft.AspNetCore.Connections;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.AddConsole();

// Add configuration to access appsettings.json or other sources
builder.Configuration.AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

// Retrieve the connection string from configuration
var connectionString = builder.Configuration.GetConnectionString("DefaultDb");

builder.Services.Configure<EndpointSettings>(builder.Configuration.GetSection("EndpointUrls"));
builder.Services.Configure<AuthSettings>(builder.Configuration.GetSection("Auth"));
builder.Services.Configure<StreamApiSettings>(builder.Configuration.GetSection("StreamApi"));

// Register the auth services
builder.Services.AddSingleton<BetfairAuthService>();
builder.Services.AddSingleton<StreamApiAuthService>();

// Register http client services
builder.Services.AddHttpClient<ICompetitionService, CompetitionService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

builder.Services.AddHttpClient<IEventService, EventService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});


builder.Services.AddHttpClient<IMarketApiService, MarketApiService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

builder.Services.AddHttpClient<IPlaceOrderService, PlaceOrderService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

builder.Services.AddHttpClient<AccountService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

builder.Services.AddHttpClient<HistoricalDataService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

builder.Services.AddHttpClient<IResultsService, ResultsService>((sp, client) =>
{
    BetfairHttpClientFactory.ConfigureBetfairClient(client, sp);
}).ConfigurePrimaryHttpMessageHandler(sp =>
{
    return BetfairHttpClientFactory.CreateBetfairHandler(sp);
});

// Register database services with the connection string
builder.Services.AddSingleton(new CompetitionDb(connectionString));
builder.Services.AddSingleton(new ListMarketCatalogueDb(connectionString));
builder.Services.AddSingleton(new MarketBookDb(connectionString));
builder.Services.AddSingleton(new EventDb2(connectionString));
builder.Services.AddSingleton(new MarketProfitAndLossDb(connectionString));
builder.Services.AddSingleton(new HistoricalDataDb(connectionString));
builder.Services.AddSingleton(new NcaaBasketballDb(connectionString));

// Register scoped services
builder.Services.AddScoped<CompetitionAutomationService>();
builder.Services.AddScoped<MarketAutomationService>();
builder.Services.AddScoped<EventAutomationService>();

// Register greyhound services
builder.Services.AddScoped<GreyhoundMarketApiService>((provider) =>
{
    var baseService = provider.GetRequiredService<IMarketApiService>();
    var logger = provider.GetRequiredService<ILogger<GreyhoundMarketApiService>>();
    var httpClient = provider.GetRequiredService<HttpClient>();
    var authService = provider.GetRequiredService<BetfairAuthService>();
    var settings = provider.GetRequiredService<IOptions<EndpointSettings>>();
    return new GreyhoundMarketApiService(baseService, logger, httpClient, authService, settings);
});
Console.WriteLine("✅ Registered GreyhoundMarketApiService");

builder.Services.AddScoped<GreyhoundAutomationService>((provider) =>
{
    var greyhoundMarketApiService = provider.GetRequiredService<GreyhoundMarketApiService>();
    var listMarketCatalogueDb = provider.GetRequiredService<ListMarketCatalogueDb>();
    var marketBookDb = provider.GetRequiredService<MarketBookDb>();
    var eventDb = provider.GetRequiredService<EventDb2>();
    return new GreyhoundAutomationService(greyhoundMarketApiService, listMarketCatalogueDb, marketBookDb, eventDb);
});
Console.WriteLine("✅ Registered GreyhoundAutomationService");

builder.Services.AddScoped<GreyhoundResultsService>();
Console.WriteLine("✅ Registered GreyhoundResultsService");

builder.Services.AddSingleton<HorseRacingAutomationService>();
//builder.Services.AddScoped<MarketBackgroundWorker>();

// Register Stream API services
builder.Services.AddSingleton<IStreamApiService, StreamApiService>();
Console.WriteLine("✅ Registered StreamApiService");

builder.Services.AddScoped<DatabaseService>(provider => new DatabaseService(connectionString));

// Register ResultsService
builder.Services.AddScoped<IResultsService, ResultsService>();

// Register Race Results Service (for exact finishing positions)
builder.Services.AddScoped<Betfair.Services.RaceResults.IRaceResultsProvider, Betfair.Services.RaceResults.Providers.TheRacingApiProvider>();
builder.Services.AddScoped<Betfair.Services.RaceResults.IRaceResultsProvider, Betfair.Services.RaceResults.Providers.RpScrapeProvider>();
builder.Services.AddScoped<Betfair.Services.RaceResults.IRaceResultsService, Betfair.Services.RaceResults.CompositeRaceResultsService>();
Console.WriteLine("✅ Registered RaceResultsService with TheRacingAPI and RPScrape providers");

// Register NCAA Basketball services
builder.Services.AddScoped<INcaaBasketballService, NcaaBasketballService>();
builder.Services.AddHttpClient<INcaaOddsService, NcaaOddsService>();

// Register hosted services
//builder.Services.AddHostedService<BetfairAutomationService>();
builder.Services.AddHostedService<MarketBackgroundWorker>();
Console.WriteLine("✅ Registered MarketBackgroundWorker");
builder.Services.AddHostedService<HorseRacingStartupService>();
Console.WriteLine("✅ Registered HorseRacingStartupService");
builder.Services.AddHostedService<GreyhoundBackgroundWorker>();
Console.WriteLine("✅ Registered GreyhoundBackgroundWorker");
builder.Services.AddHostedService<StreamApiBackgroundWorker>();
Console.WriteLine("✅ Registered StreamApiBackgroundWorker");
// NCAA workers commented out - not currently in use
// builder.Services.AddHostedService<NcaaBasketballBackgroundService>();
// Console.WriteLine("✅ Registered NcaaBasketballBackgroundService");
// builder.Services.AddHostedService<NcaaBasketballMarketWorker>();
// Console.WriteLine("✅ Registered NcaaBasketballMarketWorker");
builder.Services.AddHostedService<BspBackfillBackgroundWorker>();
Console.WriteLine("✅ Registered BspBackfillBackgroundWorker");
builder.Services.AddControllers();

// Add Swagger
builder.Services.AddSwaggerGen();

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

// Initialize SQLite and set provider
SQLitePCL.Batteries_V2.Init();
SQLitePCL.raw.SetProvider(new SQLitePCL.SQLite3Provider_e_sqlite3());

var app = builder.Build();

// TEST: Verify NCAA Basketball service dependencies can be resolved
try
{
    using var scope = app.Services.CreateScope();
    var ncaaDb = scope.ServiceProvider.GetRequiredService<NcaaBasketballDb>();
    var oddsService = scope.ServiceProvider.GetRequiredService<INcaaOddsService>();
    Console.WriteLine("✅ NCAA Basketball dependencies resolved successfully");
    
    // Now try to actually instantiate the service
    var logger = scope.ServiceProvider.GetRequiredService<ILogger<NcaaBasketballBackgroundService>>();
    var serviceProvider = scope.ServiceProvider;
    var ncaaService = new NcaaBasketballBackgroundService(logger, serviceProvider, ncaaDb);
    Console.WriteLine("✅ NCAA Basketball service instantiated successfully");
    
    // List all registered hosted services
    var hostedServices = app.Services.GetServices<Microsoft.Extensions.Hosting.IHostedService>();
    Console.WriteLine($"📊 Total hosted services registered: {hostedServices.Count()}");
    foreach (var service in hostedServices)
    {
        Console.WriteLine($"   - {service.GetType().Name}");
    }
}
catch (Exception ex)
{
    Console.WriteLine($"❌ FATAL: NCAA Basketball service failed:");
    Console.WriteLine($"   Error: {ex.Message}");
    Console.WriteLine($"   Type: {ex.GetType().Name}");
    Console.WriteLine($"   Stack: {ex.StackTrace}");
    if (ex.InnerException != null)
    {
        Console.WriteLine($"   Inner: {ex.InnerException.Message}");
    }
}

// Ensure the application uses the specified port or logs an error if unavailable
var port = Environment.GetEnvironmentVariable("PORT") ?? "5173";
try
{
    app.Urls.Add($"http://0.0.0.0:{port}");
    Console.WriteLine($"Application starting on port {port}.");
}
catch (IOException ex) when (ex.InnerException is AddressInUseException)
{
    Console.WriteLine($"Error: Port {port} is already in use. Please stop the conflicting process or specify a different port using the PORT environment variable.");
    Environment.Exit(1); // Exit the application
}

app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "API Documentation V1");
});

// Configure the HTTP request pipeline
app.UseHttpsRedirection();
app.UseRouting();
app.UseAuthorization();
app.MapControllers();
app.UseCors();
app.Run();
