namespace TARNO.UI.Models;

/// <summary>
/// Persistiertes Layout eines einzelnen UI-Panels (Explorer, Coding, Terminal, ContextDock, Chat).
/// </summary>
public class PanelLayoutModel
{
    /// <summary>Eindeutiger Panel-Typ, z. B. "explorer", "coding", "terminal", "context", "chat".</summary>
    public string PanelId { get; set; } = string.Empty;

    /// <summary>
    /// Zugehöriges Fenster: 0 = Hauptfenster, 1 = Sekundaeres Fenster, 2 = Tertiaeres Fenster.
    /// Bei Drag-and-Drop kann hier spaeter ein GUID stehen.
    /// </summary>
    public int WindowIndex { get; set; }

    /// <summary>0-basierter Display-Index, auf dem das Panel zuletzt lag.</summary>
    public int DisplayIndex { get; set; }

    /// <summary>Position und Groesse innerhalb des Zielfensters in geräteunabhängigen Pixeln.</summary>
    public RectModel Bounds { get; set; } = new();

    /// <summary>Ist das Panel sichtbar (eingeklappt vs. ausgeklappt).</summary>
    public bool IsVisible { get; set; } = true;

    /// <summary>Ist das Panel im Multi-Screen-Modus frei verschiebbar.</summary>
    public bool IsFloating { get; set; }

    // Phase 77: Lochbrett-Position und -Spanne
    public int GridX { get; set; }

    public int GridY { get; set; }

    public int GridColumns { get; set; } = 1;

    public int GridRows { get; set; } = 1;

    public double Scale { get; set; } = 1.0;
}

/// <summary>
/// Rechteck fuer JSON-Serialisierung (WinUI RectInt32 ist nicht direkt serialisierbar).
/// </summary>
public class RectModel
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }
}
