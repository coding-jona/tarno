using System;
using CommunityToolkit.Mvvm.ComponentModel;

namespace TARNO.UI.ViewModels;

/// <summary>Eine Statuskarte fuer einen einzelnen Agent-Pool-Teilnehmer in der
/// Live-Ansicht des Code-Workspace (Vorbild: Claude Codes "Hintergrundaufgaben"-
/// Kartenliste - pro Agent Rolle/Status/Laufzeit/Nachrichtenzahl statt nur
/// eines flachen Transkripts). Rein client-seitig aus PoolTranscript-Ereignissen
/// abgeleitet, keine neuen gRPC-Felder noetig.</summary>
public sealed partial class PoolAgentStatusDisplay : ObservableObject
{
    public string AgentSlug { get; init; } = string.Empty;
    public bool IsLead { get; init; }

    [ObservableProperty]
    private bool _isRunning = true;

    [ObservableProperty]
    private int _messageCount;

    [ObservableProperty]
    private string _elapsedLabel = "0:00";

    public DateTime StartedAtUtc { get; init; } = DateTime.UtcNow;

    public string RoleLabel => IsLead ? "Lead" : "Worker";

    public string StatusGlyph => IsRunning ? "⏳" : "✅";

    /// <summary>Aktualisiert Nachrichtenzahl und Laufzeit anhand des Zeitpunkts
    /// der zuletzt empfangenen Nachricht dieses Agents - kein Live-Timer,
    /// die Laufzeit "tickt" nur bei tatsaechlicher Aktivitaet weiter.</summary>
    public void RecordActivity(DateTime nowUtc)
    {
        MessageCount++;
        UpdateElapsed(nowUtc);
    }

    public void UpdateElapsed(DateTime nowUtc)
    {
        var elapsed = nowUtc - StartedAtUtc;
        if (elapsed < TimeSpan.Zero)
        {
            elapsed = TimeSpan.Zero;
        }
        ElapsedLabel = elapsed.TotalHours >= 1
            ? $"{(int)elapsed.TotalHours}:{elapsed.Minutes:D2}:{elapsed.Seconds:D2}"
            : $"{elapsed.Minutes}:{elapsed.Seconds:D2}";
    }
}
