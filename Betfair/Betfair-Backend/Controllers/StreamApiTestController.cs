using Microsoft.AspNetCore.Mvc;
using System.Net.Security;
using System.Net.Sockets;
using System.Text;

namespace Betfair.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class StreamApiTestController : ControllerBase
    {
        private readonly ILogger<StreamApiTestController> _logger;

        public StreamApiTestController(ILogger<StreamApiTestController> logger)
        {
            _logger = logger;
        }

        [HttpGet("test-ssl")]
        public async Task<IActionResult> TestSslConnection()
        {
            try
            {
                using var tcpClient = new TcpClient();
                await tcpClient.ConnectAsync("stream-api-integration.betfair.com", 443);
                
                using var sslStream = new SslStream(tcpClient.GetStream(), false);
                await sslStream.AuthenticateAsClientAsync("stream-api-integration.betfair.com");
                
                using var reader = new StreamReader(sslStream, Encoding.UTF8);
                using var writer = new StreamWriter(sslStream, Encoding.UTF8) { AutoFlush = true };
                
                // Read the connection message
                var connectionMessage = await reader.ReadLineAsync();
                _logger.LogInformation($"Received: {connectionMessage}");
                
                // Send authentication message
                var authMessage = "{\"op\":\"authentication\",\"id\":1,\"appKey\":\"test\",\"session\":\"test\"}";
                await writer.WriteLineAsync(authMessage);
                _logger.LogInformation($"Sent: {authMessage}");
                
                // Read response
                var response = await reader.ReadLineAsync();
                _logger.LogInformation($"Response: {response}");
                
                return Ok(new
                {
                    Success = true,
                    ConnectionMessage = connectionMessage,
                    AuthResponse = response
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "SSL connection test failed");
                return BadRequest(new
                {
                    Success = false,
                    Error = ex.Message
                });
            }
        }
    }
}