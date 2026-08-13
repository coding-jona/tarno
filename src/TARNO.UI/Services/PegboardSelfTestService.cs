using System;
using System.Linq;
using TARNO.UI.Controls;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Automatisierter Selbsttest fuer das SnapCanvas/Pegboard-Drag-System.
/// Treibt exakt dieselbe Logik wie ein echter Pointer-Drag (StartDrag/Move/End
/// in PegboardDragService), aber mit einem synthetischen Windows.Foundation.
/// Point statt eines echten (nicht konstruierbaren) PointerPoint - laeuft also
/// vollstaendig ohne Maus/Touch und ohne manuelles Testen durch den Nutzer.
/// Ergebnis landet strukturiert im InteractionLogger, damit es sich per
/// Log-Datei auswerten laesst, statt per Bildschirm-Beobachtung.
/// </summary>
public static class PegboardSelfTestService
{
    private const string Tag = "PEGBOARD_TEST";

    /// <summary>
    /// Simuliert: das "coding"-Panel wird an den linken Rand des "chat"-Panels
    /// gezogen. Erwartung nach dem Tiling-Reflow-Fix: beide Panels landen
    /// nebeneinander ohne Ueberlappung, und keins bleibt bei (0,0) haengen.
    /// </summary>
    public static void Run(SnapCanvas canvas)
    {
        try
        {
            if (canvas is null)
            {
                InteractionLogger.Warn(Tag, "canvas ist null - Test uebersprungen.");
                return;
            }

            var panels = canvas.Children.OfType<IPegboardPanel>().ToList();
            InteractionLogger.Info(Tag, $"=== Selbsttest Start === Panels={panels.Count}, CanvasSize={canvas.ActualWidth:F0}x{canvas.ActualHeight:F0}, GridSize={canvas.GridSize}");

            foreach (var p in panels)
            {
                LogRect(canvas, p, "vorher");
            }

            var coding = panels.FirstOrDefault(p => p.PanelId == "coding");
            var chat = panels.FirstOrDefault(p => p.PanelId == "chat");
            var terminal = panels.FirstOrDefault(p => p.PanelId == "terminal");

            if (coding is null || chat is null)
            {
                InteractionLogger.Warn(Tag, "Panel 'coding' oder 'chat' nicht im Canvas gefunden - Test uebersprungen (falsche Seite aktiv?).");
                return;
            }

            RunScenario(canvas, coding, chat, "coding->chat (Left-Zone)", zoneFractionX: 0.05, zoneFractionY: 0.5);

            InteractionLogger.Info(Tag, "--- Zustand nach Szenario 1 ---");
            foreach (var p in panels)
            {
                LogRect(canvas, p, "nachher");
            }

            var validation = canvas.ValidateLayout();
            if (validation.IsValid)
            {
                InteractionLogger.Info(Tag, "ERGEBNIS Szenario 1: OK - keine Ueberlappung, kein Panel bei (0,0) haengengeblieben.");
            }
            else
            {
                InteractionLogger.Warn(Tag, $"ERGEBNIS Szenario 1: FEHLGESCHLAGEN - {validation}");
            }

            if (terminal is not null)
            {
                RunScenario(canvas, terminal, chat, "terminal->chat (Bottom-Zone)", zoneFractionX: 0.5, zoneFractionY: 0.95);

                InteractionLogger.Info(Tag, "--- Zustand nach Szenario 2 ---");
                foreach (var p in panels)
                {
                    LogRect(canvas, p, "nachher");
                }

                var validation2 = canvas.ValidateLayout();
                if (validation2.IsValid)
                {
                    InteractionLogger.Info(Tag, "ERGEBNIS Szenario 2: OK.");
                }
                else
                {
                    InteractionLogger.Warn(Tag, $"ERGEBNIS Szenario 2: FEHLGESCHLAGEN - {validation2}");
                }
            }

            InteractionLogger.Info(Tag, "=== Selbsttest Ende ===");
        }
        catch (Exception ex)
        {
            InteractionLogger.Error(Tag, $"Selbsttest-Exception: {ex}");
        }
    }

    private static void RunScenario(SnapCanvas canvas, IPegboardPanel dragged, IPegboardPanel target, string label, double zoneFractionX, double zoneFractionY)
    {
        InteractionLogger.Info(Tag, $"Szenario: {label}");

        var draggedRect = canvas.GetChildRect(dragged.DragRoot);
        var targetRect = canvas.GetChildRect(target.DragRoot);

        // Startpunkt: irgendwo im Header-Bereich des gezogenen Panels (oben-links + kleiner Versatz).
        var startPoint = new Windows.Foundation.Point(draggedRect.X + 20, draggedRect.Y + 10);

        // Zielpunkt: Bruchteil der Zielflaeche, um eine bestimmte Dock-Zone zu treffen.
        var dropPoint = new Windows.Foundation.Point(
            targetRect.X + targetRect.Width * zoneFractionX,
            targetRect.Y + targetRect.Height * zoneFractionY);

        InteractionLogger.Info(Tag, $"  Start={startPoint.X:F0},{startPoint.Y:F0}  Drop={dropPoint.X:F0},{dropPoint.Y:F0}");

        PegboardDragService.StartDrag(canvas, dragged.DragRoot, startPoint);
        PegboardDragService.Move(dropPoint);
        PegboardDragService.End();

        canvas.UpdateLayout();
    }

    private static void LogRect(SnapCanvas canvas, IPegboardPanel panel, string phase)
    {
        var rect = canvas.GetChildRect(panel.DragRoot);
        InteractionLogger.Info(
            Tag,
            $"  {phase} {panel.PanelId}: X={rect.X:F0},Y={rect.Y:F0},W={rect.Width:F0},H={rect.Height:F0} " +
            $"Grid=({SnapCanvas.GetGridX(panel.DragRoot)},{SnapCanvas.GetGridY(panel.DragRoot)}) " +
            $"Cells=({SnapCanvas.GetGridColumns(panel.DragRoot)}x{SnapCanvas.GetGridRows(panel.DragRoot)})");
    }
}
