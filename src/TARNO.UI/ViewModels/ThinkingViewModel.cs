using CommunityToolkit.Mvvm.ComponentModel;
using System;

namespace TARNO.UI.ViewModels;

/// <summary>
/// Represents the backend "thinking" / processing indicator state.
/// Visualized as a typing/thinking indicator in Chat and Voice pages.
/// </summary>
public partial class ThinkingViewModel : ObservableObject
{
    [ObservableProperty]
    private bool _isActive;

    [ObservableProperty]
    private string _message = string.Empty;

    [ObservableProperty]
    private string _reasoning = string.Empty;

    /// <summary>Maschinenlesbarer Schritt-Schlüssel ("llm_call"/"tool_exec"/
    /// "tool_followup"/"reasoning") - treibt die Orb-Farbwahl, getrennt vom
    /// deutschen Anzeigetext in <see cref="Message"/>.</summary>
    [ObservableProperty]
    private string _stageKey = string.Empty;

    [ObservableProperty]
    private DateTimeOffset _startedAt;
}
