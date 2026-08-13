using System.Collections.Generic;

namespace TARNO.UI.Models;

/// <summary>
/// Gesamtes Multi-Screen-/Lochbrett-Layout: welche Panels auf welchen Fenstern
/// und Displays liegen und wie gross sie sind.
/// </summary>
public class MultiScreenLayoutModel
{
    /// <summary>Schema-Version fuer Migrationen.</summary>
    public int Version { get; set; } = 1;

    /// <summary>Name des gespeicherten Profils (z. B. "Standard", "Work", "Home").</summary>
    public string ProfileName { get; set; } = "Standard";

    /// <summary>Anzahl der beim Speichern genutzten Displays.</summary>
    public int DisplayCount { get; set; } = 1;

    /// <summary>Alle bekannten Panels mit ihrer Position.</summary>
    public List<PanelLayoutModel> Panels { get; set; } = new();

    /// <summary>Snapshot der Hauptfenster-Groesse/-Position.</summary>
    public RectModel MainWindowBounds { get; set; } = new();
}
