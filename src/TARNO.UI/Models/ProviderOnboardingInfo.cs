using System;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace TARNO.UI.Models;

public sealed class ProviderOnboardingInfo
{
    [JsonPropertyName("provider")]
    public string Provider { get; set; } = string.Empty;

    [JsonPropertyName("label")]
    public string Label { get; set; } = string.Empty;

    [JsonPropertyName("dashboardUrl")]
    public string DashboardUrl { get; set; } = string.Empty;

    [JsonPropertyName("keyPattern")]
    public string KeyPattern { get; set; } = string.Empty;

    [JsonPropertyName("instructions")]
    public string Instructions { get; set; } = string.Empty;

    [JsonIgnore]
    public Regex? KeyRegex
    {
        get
        {
            try
            {
                if (!string.IsNullOrWhiteSpace(KeyPattern))
                {
                    return new Regex(KeyPattern, RegexOptions.Compiled | RegexOptions.CultureInvariant);
                }
            }
            catch
            {
                // Falls das Pattern ungültig ist, liefern wir null statt eine Exception.
            }
            return null;
        }
    }
}
