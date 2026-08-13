using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;
using TARNO.UI.Controls;
using TARNO.UI.MultiScreen;

namespace TARNO.UI.Services;

/// <summary>
/// Diagnose- und Testfunktionen für das SnapCanvas/DraggableSection-Layout.
/// Kann ohne Nutzer-UI aufgerufen werden und protokolliert das Ergebnis.
/// </summary>
public static class LayoutDiagnosticsService
{
    /// <summary>
    /// Prüft jedes registrierte Fenster auf ein SnapCanvas und validiert dessen Layout.
    /// </summary>
    public static void ValidateAllWindows()
    {
        bool any = false;
        foreach (var window in WindowStateCoordinator.Windows)
        {
            if (window?.Content is not UIElement root)
            {
                continue;
            }

            var canvas = FindSnapCanvas(root);
            if (canvas is null)
            {
                continue;
            }

            any = true;
            var result = canvas.ValidateLayout();
            string windowName = window is MainWindow ? "MainWindow" : $"PanelWindow-{WindowStateCoordinator.GetWindowIndex(window)}";
            if (result.IsValid)
            {
                InteractionLogger.Info("LAYOUT_DIAG", $"{windowName}: Layout gültig ({canvas.Children.Count} Kinder, GridSize={canvas.GridSize}).");
            }
            else
            {
                InteractionLogger.Warn("LAYOUT_DIAG", $"{windowName}: {result}");
            }

            DescribeChildren(canvas, windowName);
        }

        if (!any)
        {
            InteractionLogger.Warn("LAYOUT_DIAG", "Keine Fenster mit SnapCanvas gefunden.");
        }
    }

    /// <summary>
    /// Protokolliert die Position und Größe aller Kinder eines SnapCanvas.
    /// Dient als selbstständige Überprüfung, ohne dass ein Mensch die Grafik sehen muss.
    /// </summary>
    public static void DescribeChildren(SnapCanvas canvas, string context)
    {
        foreach (var child in canvas.Children)
        {
            if (child is null || SnapCanvas.GetIsAdorner(child))
            {
                continue;
            }

            var rect = canvas.GetChildRect(child);
            string name = child is FrameworkElement fe && !string.IsNullOrEmpty(fe.Name)
                ? fe.Name
                : child.GetType().Name;
            InteractionLogger.Info(
                "LAYOUT_DIAG",
                $"{context}/{name}: X={rect.X:F0}, Y={rect.Y:F0}, W={rect.Width:F0}, H={rect.Height:F0}, " +
                $"Grid=({SnapCanvas.GetGridX(child)},{SnapCanvas.GetGridY(child)}), " +
                $"Cells=({SnapCanvas.GetGridColumns(child)}x{SnapCanvas.GetGridRows(child)}), Scale={SnapCanvas.GetScale(child):F2}");
        }
    }

    /// <summary>
    /// Testet die MultiScreen-Erkennung anhand simulierter Punkte, ohne Fenster zu verschieben.
    /// </summary>
    public static void TestMultiScreenDetection()
    {
        var displays = MultiScreenLayoutService.GetDisplays();
        InteractionLogger.Info("LAYOUT_DIAG", $"Erkannte Displays: {displays.Count}");
        for (int i = 0; i < displays.Count; i++)
        {
            var work = displays[i].WorkArea;
            InteractionLogger.Info(
                "LAYOUT_DIAG",
                $"Display {i}: WorkArea={work.X},{work.Y} {work.Width}x{work.Height}");

            var center = new Windows.Graphics.PointInt32(work.X + work.Width / 2, work.Y + work.Height / 2);
            int detected = MultiScreenLayoutService.FindDisplayForPoint(center);
            InteractionLogger.Info("LAYOUT_DIAG", $"Display {i} Zentrum -> erkannt als Display {detected}");
        }
    }

    private static SnapCanvas? FindSnapCanvas(UIElement root)
    {
        if (root is SnapCanvas canvas)
        {
            return canvas;
        }

        int count = VisualTreeHelper.GetChildrenCount(root);
        for (int i = 0; i < count; i++)
        {
            if (VisualTreeHelper.GetChild(root, i) is UIElement child)
            {
                var found = FindSnapCanvas(child);
                if (found is not null)
                {
                    return found;
                }
            }
        }

        return null;
    }
}
