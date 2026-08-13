namespace TARNO.UI.Models;

/// <summary>
/// Erweitert ein draggable Panel um Snap-to-Grid-Informationen,
/// die nötig sind, um es im Lochbrett (SnapCanvas) zu platzieren,
/// zu skalieren und wiederzufinden.
/// </summary>
public interface IPegboardPanel : IDraggablePanel
{
    int GridX { get; set; }
    int GridY { get; set; }
    int GridColumns { get; set; }
    int GridRows { get; set; }
    double Scale { get; set; }
    bool IsPegged { get; }

    /// <summary>
    /// Gibt eine laufende Pointer-Capture des Drag-Headers frei. Muss vor
    /// jedem Reparenting in ein anderes Fenster (Tear-off, Pop-out) erfolgen:
    /// WinUI-Pointer-Capture ist an das ursprüngliche Fenster gebunden - bleibt
    /// sie während des Reparentings bestehen, wirft das nächste PointerMoved/
    /// PointerReleased-Ereignis beim Routing auf den nun fensterfremden
    /// Header, was die App abstürzen lässt.
    /// </summary>
    void ReleaseDragCapture();
}
