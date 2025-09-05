using Betfair.Data;
using Betfair.Services.ML;
using Betfair.Services.Simulation;
using Betfair.Extensions;
using Microsoft.EntityFrameworkCore;

namespace Betfair.Simulation
{
    /// <summary>
    /// Simple Program class for testing ONLY the simulation system
    /// This bypasses all Betfair API dependencies to focus on simulation testing
    /// </summary>
    public class SimulationProgram
    {
        public static void Main(string[] args)
        {
            var builder = WebApplication.CreateBuilder(args);
            builder.Logging.AddConsole();

            // Add configuration
            builder.Configuration.AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

            // Add simulation database
            var simulationConnectionString = builder.Configuration.GetConnectionString("SimulationDatabase") ?? "Data Source=simulation.db";
            builder.Services.AddDbContext<SimulationDbContext>(options =>
                options.UseSqlite(simulationConnectionString));

            // Add ML services
            builder.Services.AddMLServices(builder.Configuration);

            // Add simulation services
            builder.Services.AddScoped<IBettingSimulationService, BettingSimulationService>();

            // Add controllers
            builder.Services.AddControllers();

            // Add Swagger for testing
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

            // Initialize SQLite
            SQLitePCL.Batteries_V2.Init();
            SQLitePCL.raw.SetProvider(new SQLitePCL.SQLite3Provider_e_sqlite3());

            var app = builder.Build();

            // Create database if it doesn't exist
            using (var scope = app.Services.CreateScope())
            {
                var context = scope.ServiceProvider.GetRequiredService<SimulationDbContext>();
                context.Database.EnsureCreated();
                Console.WriteLine("✅ Simulation database initialized");
            }

            // Set port
            var port = Environment.GetEnvironmentVariable("PORT") ?? "5174"; // Different port to avoid conflicts
            app.Urls.Add($"http://0.0.0.0:{port}");
            Console.WriteLine($"🎰 Simulation API starting on port {port}");

            app.UseSwagger();
            app.UseSwaggerUI(c =>
            {
                c.SwaggerEndpoint("/swagger/v1/swagger.json", "Betting Simulation API V1");
            });

            app.UseRouting();
            app.UseAuthorization();
            app.MapControllers();
            app.UseCors();

            Console.WriteLine("🚀 Betting Simulation API Ready!");
            Console.WriteLine($"📊 Swagger UI: http://localhost:{port}/swagger");
            Console.WriteLine($"🎯 Test endpoint: http://localhost:{port}/api/simulation/summary");

            app.Run();
        }
    }
}
