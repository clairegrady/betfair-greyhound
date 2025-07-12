using System.Text.Json.Serialization;

namespace Betfair.Models;
public class ApiResponse<T>
{
    [JsonPropertyName("result")]
    public List<T> Result { get; set; }
}