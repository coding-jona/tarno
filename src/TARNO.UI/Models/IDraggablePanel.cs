using Microsoft.UI.Xaml;

namespace TARNO.UI.Models;

/// <summary>
/// Gemeinsame Schnittstelle für alle UI-Bereiche, die der Nutzer per
/// Drag-and-Drop in ein anderes Fenster oder eine andere Zone ziehen darf.
/// </summary>
public interface IDraggablePanel
{
    /// <summary>Eindeutige Kennung im Layout-Speicher.</summary>
    string PanelId { get; }

    /// <summary>Anzeigename für Fenster-Titel/Header.</summary>
    string Title { get; }

    /// <summary>Aktueller Fenster-Index (0 = Hauptfenster).</summary>
    int WindowIndex { get; set; }

    /// <summary>Das eigentliche UI-Element, das umgehängt werden kann.</summary>
    FrameworkElement DragRoot { get; }

    /// <summary>Optionaler Platzhalter im ursprünglichen Layout.</summary>
    FrameworkElement? Placeholder { get; set; }
}
