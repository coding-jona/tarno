using CommunityToolkit.Mvvm.ComponentModel;
using System;

namespace TARNO.UI.ViewModels;

/// <summary>
/// UI-facing representation of one AgentTrace item for the ThoughtStream timeline.
/// </summary>
public partial class AgentTraceViewModel : ObservableObject
{
    [ObservableProperty]
    private string _traceId = string.Empty;

    [ObservableProperty]
    private string _parentId = string.Empty;

    [ObservableProperty]
    private string _turnId = string.Empty;

    [ObservableProperty]
    private DateTime _timestamp;

    /// <summary>thought_delta | tool_start | tool_end | file_diff</summary>
    [ObservableProperty]
    private string _traceType = string.Empty;

    [ObservableProperty]
    private string _title = string.Empty;

    [ObservableProperty]
    private string _content = string.Empty;

    [ObservableProperty]
    private string _target = string.Empty;

    [ObservableProperty]
    private string _description = string.Empty;

    [ObservableProperty]
    private bool _isCollapsed = true;

    [ObservableProperty]
    private bool _isFinished;

    [ObservableProperty]
    private bool _success = true;

    [ObservableProperty]
    private string _resultSummary = string.Empty;

    [ObservableProperty]
    private string _language = string.Empty;

    [ObservableProperty]
    private bool _isNewFile;

    /// <summary>Icon glyph for the timeline bullet.</summary>
    public string Icon => TraceType switch
    {
        "thought_delta" => "🧠",
        "tool_start" => "▶",
        "tool_end" => "✓",
        "file_diff" => "📝",
        _ => "•"
    };
}
