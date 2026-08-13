using System;
using System.Linq;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using TARNO.UI.Controls;
using TARNO.UI.Models;
using TARNO.UI.MultiScreen;
using TARNO.UI.ViewModels;

namespace TARNO.UI.Services;

/// <summary>
/// Entfernt ein Panel aus einem SnapCanvas und öffnet es in einem eigenen
/// PanelWindow auf einem Ziel-Monitor (default: zweiter Bildschirm, falls
/// vorhanden, sonst primärer Bildschirm).
/// </summary>
public static class PegboardService
{
    public static void PopOutToMonitor(IPegboardPanel panel)
    {
        if (panel?.DragRoot?.Parent is not SnapCanvas canvas)
        {
            return;
        }

        if (WindowStateCoordinator.MainWindow is not MainWindow main)
        {
            return;
        }

        var viewModel = main.ViewModel;
        if (viewModel is null)
        {
            return;
        }

        var displays = MultiScreenLayoutService.GetDisplays();
        int displayIndex = displays.Count > 1 ? 1 : 0;
        var workArea = MultiScreenLayoutService.GetWorkArea(displayIndex);

        const int width = 600;
        const int height = 400;
        int x = workArea.X + Math.Max(0, (workArea.Width - width) / 2);
        int y = workArea.Y + Math.Max(0, (workArea.Height - height) / 2);

        var bounds = new RectModel
        {
            X = x,
            Y = y,
            Width = width,
            Height = height,
        };

        var root = panel.DragRoot;
        _ = canvas.Children.Remove(root);

        var window = new PanelWindow(viewModel);
        window.Host(root, panel.PanelId);
        panel.WindowIndex = window.WindowIndex;

        MultiScreenLayoutService.PositionWindow(window.AppWindow, bounds);
        window.Activate();

        SavePanelLayout(panel);
        InteractionLogger.Info("PEGBOARD", $"Panel '{panel.PanelId}' auf Monitor {displayIndex} ausgelagert.");
    }

    /// <summary>
    /// Dockt ein Panel wieder in das SnapCanvas des Hauptfensters ein.
    /// Wird für Phase 78 benötigt (zurück aus Pop-Out-Fenster).
    /// </summary>
    public static void DockToMain(IPegboardPanel panel, int gridX, int gridY)
    {
        if (panel?.DragRoot is null)
        {
            return;
        }

        if (FindSnapCanvasInMain() is not SnapCanvas canvas)
        {
            return;
        }

        var root = panel.DragRoot;
        if (root.Parent is Panel panelParent)
        {
            _ = panelParent.Children.Remove(root);
        }
        else if (root.Parent is ContentControl cc)
        {
            cc.Content = null;
        }
        else if (root.Parent is Border border)
        {
            border.Child = null;
        }

        panel.WindowIndex = WindowStateCoordinator.MainWindowIndex;
        SnapCanvas.SetGridX(root, gridX);
        SnapCanvas.SetGridY(root, gridY);

        if (!canvas.Children.Contains(root))
        {
            canvas.Children.Add(root);
        }

        canvas.InvalidateMeasure();
        SavePanelLayout(panel);
    }

    /// <summary>
    /// Speichert Position, Größe, Skalierung und Fensterzugehörigkeit eines
    /// Lochbrett-Panels in der Layout-Datei.
    /// </summary>
    public static void SavePanelLayout(IPegboardPanel? panel)
    {
        if (panel?.DragRoot is null)
        {
            return;
        }

        var main = WindowStateCoordinator.MainWindow as MainWindow;
        var profile = main?.ViewModel?.Settings.ActiveLayoutProfile;

        var layout = LayoutStore.Load(profile);
        var existing = layout.Panels.FirstOrDefault(p => p.PanelId == panel.PanelId);
        if (existing is null)
        {
            existing = new PanelLayoutModel { PanelId = panel.PanelId };
            layout.Panels.Add(existing);
        }

        existing.WindowIndex = panel.WindowIndex;
        existing.GridX = SnapCanvas.GetGridX(panel.DragRoot);
        existing.GridY = SnapCanvas.GetGridY(panel.DragRoot);
        existing.GridColumns = SnapCanvas.GetGridColumns(panel.DragRoot);
        existing.GridRows = SnapCanvas.GetGridRows(panel.DragRoot);
        existing.Scale = SnapCanvas.GetScale(panel.DragRoot);

        LayoutStore.Save(layout, profile);
    }

    /// <summary>
    /// Wiederherstellung der bekannten Panel-Positionen in einem SnapCanvas.
    /// Panels ohne Eintrag behalten ihre XAML-Defaults.
    /// </summary>
    public static void RestoreLayout(SnapCanvas canvas)
    {
        if (WindowStateCoordinator.MainWindow is not MainWindow main)
        {
            return;
        }

        var profile = main.ViewModel?.Settings.ActiveLayoutProfile;
        var layout = LayoutStore.Load(profile);

        foreach (UIElement child in canvas.Children)
        {
            if (child is not IPegboardPanel panel)
            {
                continue;
            }

            var saved = layout.Panels.FirstOrDefault(p => p.PanelId == panel.PanelId);
            if (saved is null)
            {
                continue;
            }

            panel.WindowIndex = saved.WindowIndex;
            SnapCanvas.SetGridX(panel.DragRoot, saved.GridX);
            SnapCanvas.SetGridY(panel.DragRoot, saved.GridY);
            SnapCanvas.SetGridColumns(panel.DragRoot, saved.GridColumns);
            SnapCanvas.SetGridRows(panel.DragRoot, saved.GridRows);
            SnapCanvas.SetScale(panel.DragRoot, saved.Scale);
        }

        canvas.InvalidateMeasure();
    }

    private static SnapCanvas? FindSnapCanvasInMain()
    {
        if (WindowStateCoordinator.MainWindow is not MainWindow main)
        {
            return null;
        }

        if (main.ContentFrame?.Content is not UIElement pageRoot)
        {
            return null;
        }

        return FindSnapCanvas(pageRoot);
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
