namespace TARNO.UI.ViewModels;

/// <summary>Ein Eintrag in der Live-Swimlane-Ansicht eines Agent-Pool-Laufs
/// (siehe ChatPage.xaml Pool-Panel). KindLabel ist die deutsche Beschriftung
/// fuer das kind-Feld aus PoolMessageEventArgs.</summary>
public sealed class PoolMessageDisplay
{
    public string FromAgent { get; init; } = string.Empty;
    public string ToAgent { get; init; } = string.Empty;
    public string Kind { get; init; } = string.Empty;
    public string Text { get; init; } = string.Empty;
    public string SubTaskId { get; init; } = string.Empty;
    public bool IsLead { get; init; }

    public string KindLabel => Kind switch
    {
        "assign" => "Zuweisung",
        "report" => "Bericht",
        "question" => "Frage",
        "merge_decision" => "Zusammenführung",
        "status" => "Status",
        _ => Kind,
    };

    /// <summary>Vorformatierte Kopfzeile - ein einzelnes x:Bind statt
    /// mehrerer verschachtelter Run-Elemente im DataTemplate.</summary>
    public string HeaderText => $"{FromAgent} → {ToAgent} · {KindLabel}";
}
