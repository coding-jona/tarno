namespace TARNO.UI.ViewModels;

/// <summary>
/// Phase 1-6: one selectable model within a provider's curated catalog,
/// as shown in the two-level provider/model picker (label, rate-limit
/// estimate, 1-3 capability keywords).
/// </summary>
public sealed class ModelOptionViewModel
{
    public string Id { get; init; } = string.Empty;
    public string Label { get; init; } = string.Empty;
    public string RateLimitNote { get; init; } = string.Empty;
    public string Capabilities { get; init; } = string.Empty;
}
