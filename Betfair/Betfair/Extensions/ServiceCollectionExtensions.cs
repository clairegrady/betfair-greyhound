using Betfair.Services.ML;

namespace Betfair.Extensions;

/// <summary>
/// Extension methods for service registration
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Add ML prediction services to dependency injection
    /// </summary>
    public static IServiceCollection AddMLServices(this IServiceCollection services, IConfiguration configuration)
    {
        // Register HTTP client for ML API
        services.AddHttpClient<IMLPredictionService, MLPredictionService>();
        
        // Register ML prediction service
        services.AddScoped<IMLPredictionService, MLPredictionService>();
        
        return services;
    }
}
