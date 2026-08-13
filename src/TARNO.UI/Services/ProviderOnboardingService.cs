using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

public static class ProviderOnboardingService
{
    private static readonly JsonSerializerOptions _options = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public static IReadOnlyList<ProviderOnboardingInfo> LoadAll()
    {
        try
        {
            string path = Path.Combine(AppContext.BaseDirectory, "Assets", "provider_onboarding.json");
            if (!File.Exists(path))
            {
                return new List<ProviderOnboardingInfo>();
            }

            string json = File.ReadAllText(path);
            var wrapper = JsonSerializer.Deserialize<ProviderOnboardingList>(json, _options);
            return wrapper?.Providers?.AsReadOnly() ?? new List<ProviderOnboardingInfo>().AsReadOnly();
        }
        catch
        {
            return new List<ProviderOnboardingInfo>().AsReadOnly();
        }
    }

    public static ProviderOnboardingInfo? Get(string provider)
    {
        return LoadAll().FirstOrDefault(
            p => p.Provider.Equals(provider, StringComparison.OrdinalIgnoreCase)
        );
    }

    private sealed class ProviderOnboardingList
    {
        [JsonPropertyName("providers")]
        public List<ProviderOnboardingInfo>? Providers { get; set; }
    }
}
