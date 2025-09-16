using Betfair.Data;
using Betfair.Services;
using Betfair.AutomationServices;
using Betfair.AutomatedServices;
using Betfair.Handlers;
using Betfair.Services.Account;
using Betfair.Services.HistoricalData;
using Betfair.Services.ML;
using Betfair.Services.Simulation;
using Betfair.Extensions;
using Betfair.Settings;
using Microsoft.AspNetCore.Connections;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.AddConsole();

// Add configuration to access appsettings.json or other sources
builder.Configuration.AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

// Retrieve the connection string from configuration
var connectionString = builder.Configuration.GetConnectionString("DefaultDb");

builder.Services.Configure<EndpointSettings>(builder.Configuration.GetSection("EndpointUrls"));
builder.Services.Configure<AuthSettings>(builder.Configuration.GetSection("Auth"));

// Register the auth service
builder.Services.AddSingleton<BetfairAuthService>();

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

// Register database services with the connection string
builder.Services.AddSingleton(new CompetitionDb(connectionString));
builder.Services.AddSingleton(new ListMarketCatalogueDb(connectionString));
builder.Services.AddSingleton(new MarketBookDb(connectionString));
builder.Services.AddSingleton(new EventDb2(connectionString));
builder.Services.AddSingleton(new MarketProfitAndLossDb(connectionString));
builder.Services.AddSingleton(new HistoricalDataDb(connectionString));

// Add simulation database
var simulationConnectionString = builder.Configuration.GetConnectionString("SimulationDatabase") ?? "Data Source=simulation.db";
builder.Services.AddDbContext<SimulationDbContext>(options =>
    options.UseSqlite(simulationConnectionString));

// Add ML services
builder.Services.AddMLServices(builder.Configuration);

// Add simulation services
builder.Services.AddScoped<IBettingSimulationService, BettingSimulationService>();

// Register scoped services
builder.Services.AddScoped<CompetitionAutomationService>();
builder.Services.AddScoped<MarketAutomationService>();
builder.Services.AddScoped<EventAutomationService>();
builder.Services.AddScoped<GreyhoundAutomationService>();
builder.Services.AddSingleton<HorseRacingAutomationService>();
//builder.Services.AddScoped<MarketBackgroundWorker>();

// Register hosted services
//builder.Services.AddHostedService<BetfairAutomationService>();
builder.Services.AddHostedService<MarketBackgroundWorker>();
builder.Services.AddHostedService<HorseRacingStartupService>();

builder.Services.AddScoped<DatabaseService>(provider => new DatabaseService(connectionString));

// Add controllers
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
