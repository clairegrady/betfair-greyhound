using System.Text.Json.Serialization;

namespace Betfair.Models.Runner;
public class RunnerDescription
{
    [JsonPropertyName("selectionId")]
    public long SelectionId { get; set; }

    [JsonPropertyName("runnerName")]
    public string RunnerName { get; set; }

    [JsonPropertyName("metadata")]
    public RunnerMetadata Metadata { get; set; }
}

