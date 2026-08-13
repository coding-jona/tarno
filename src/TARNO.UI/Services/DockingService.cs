using System;
using System.Linq;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using TARNO.UI;
using TARNO.UI.Models;
using TARNO.UI.MultiScreen;
using TARNO.UI.Pages;
using TARNO.UI.UserControls;
using TARNO.UI.ViewModels;

namespace TARNO.UI.Services;

/// <summary>
/// Zentrale Docking-Logik (Phase 38): entfernt ein beliebiges Panel aus
/// seinem aktuellen Eltern-Element und platziert es in einem Zielfenster
/// oder Dock-Zone. Unterstützt freies Floating und Rückkehr über einen
/// Platzhalter im ursprünglichen Layout.
/// </summary>
public static class DockingService
{
    private static MainViewModel? _viewModel;

    public static void Initialize(MainViewModel viewModel)
    {
        _viewModel = viewModel;
        PanelDragService.PanelDropRequested += OnPanelDropRequested;
    }

    private static void OnPanelDropRequested(object? sender, PanelDragService.PanelDropRequest e)
    {
        if (_viewModel is null)
        {
            return;
        }

        var payload = e.Payload;

        var panel = FindDraggablePanel(payload.PanelId, payload.SourceWindowIndex);
        if (panel is null)
        {
            return;
        }

        if (payload.SourceWindowIndex == e.TargetWindowIndex)
        {
            // Gleiches Fenster: in MainWindow -> ins eigene Floating-Fenster lösen.
            if (e.TargetWindowIndex == WindowStateCoordinator.MainWindowIndex)
            {
                UndockToNewWindow(panel, e.Args);
            }
            return;
        }

        RemoveFromCurrentParent(panel, createPlaceholder: !IsTypedPanel(panel));

        if (e.TargetWindowIndex == WindowStateCoordinator.MainWindowIndex)
        {
            DockToMain(panel);
        }
        else if (WindowStateCoordinator.GetWindowByIndex(e.TargetWindowIndex) is Window targetWindow)
        {
            HostInWindow(panel, targetWindow, e.Args);
        }

        SaveLayoutSnapshot(payload.PanelId, panel.WindowIndex);
    }

    public static void UndockToNewWindow(IDraggablePanel panel, DragEventArgs e)
    {
        var point = e.GetPosition(null);
        var bounds = new RectModel
        {
            X = (int)point.X,
            Y = (int)point.Y,
            Width = 800,
            Height = 600,
        };
        UndockToNewWindow(panel, 1, bounds);
    }

    public static void UndockToNewWindow(IDraggablePanel panel, int displayIndex = 1, RectModel? bounds = null, bool createPlaceholder = true)
    {
        if (_viewModel is null)
        {
            return;
        }

        RemoveFromCurrentParent(panel, createPlaceholder: createPlaceholder && !IsTypedPanel(panel));

        var window = new PanelWindow(_viewModel);
        window.Host(panel.DragRoot, panel.PanelId);
        panel.WindowIndex = window.WindowIndex;

        if (bounds is not null && bounds.Width > 0 && bounds.Height > 0)
        {
            MultiScreenLayoutService.PositionWindow(window.AppWindow, bounds);
        }
        else
        {
            MultiScreenLayoutService.PositionWindowOnDisplay(window.AppWindow, displayIndex);
        }

        window.Activate();
        SaveLayoutSnapshot(panel.PanelId, window.WindowIndex, bounds);
    }

    /// <summary>
    /// Stellt das zuletzt gespeicherte Layout wieder her (freie Panel-Fenster).
    /// Wird beim Laden der Hauptseite(n) aufgerufen und sucht im aktuell
    /// geladenen ContentFrame nach allen bekannten Panels.
    /// </summary>
    public static void RestoreLayout()
    {
        if (_viewModel is null)
        {
            return;
        }

        var main = WindowStateCoordinator.MainWindow as MainWindow;
        var root = main?.ContentFrame?.Content as UIElement;
        if (root is null)
        {
            return;
        }

        var layout = GetCurrentLayout();
        foreach (var panelLayout in layout.Panels)
        {
            if (panelLayout.WindowIndex == 0)
            {
                continue;
            }

            var panel = FindDraggablePanelInTree(root, panelLayout.PanelId);
            if (panel is null)
            {
                continue;
            }

            if (panel.DragRoot.Parent is not Panel parent)
            {
                continue;
            }

            UndockToNewWindow(panel, panelLayout.DisplayIndex, panelLayout.Bounds);
        }
    }

    public static void SavePanelBounds(string panelId, int windowIndex, RectModel bounds)
    {
        SaveLayoutSnapshot(panelId, windowIndex, bounds);
    }

    private static void DockToMain(IDraggablePanel panel)
    {
        if (panel is IPegboardPanel pegboardPanel)
        {
            PegboardService.DockToMain(pegboardPanel, 0, 0);
        }
        else if (panel.Placeholder is not null)
        {
            RestoreFromPlaceholder(panel);
        }

        panel.WindowIndex = WindowStateCoordinator.MainWindowIndex;
    }

    private static void HostInWindow(IDraggablePanel panel, Window targetWindow, DragEventArgs? e)
    {
        if (targetWindow is PanelWindow panelWindow)
        {
            panelWindow.Host(panel.DragRoot, panel.PanelId);
            panel.WindowIndex = panelWindow.WindowIndex;
        }
        else
        {
            HostInNewWindow(panel, e);
        }
    }

    private static void HostInNewWindow(IDraggablePanel panel, DragEventArgs? e = null)
    {
        if (_viewModel is null)
        {
            return;
        }

        var window = new PanelWindow(_viewModel);
        window.Host(panel.DragRoot, panel.PanelId);
        panel.WindowIndex = window.WindowIndex;

        if (e is not null)
        {
            var point = e.GetPosition(null);
            var bounds = new RectModel
            {
                X = (int)point.X,
                Y = (int)point.Y,
                Width = 800,
                Height = 600,
            };
            MultiScreenLayoutService.PositionWindow(window.AppWindow, bounds);
        }

        window.Activate();
    }

    private static bool IsTypedPanel(IDraggablePanel panel)
    {
        return panel is ExplorerPanelControl
            or ContextDockPanelControl
            or CodingPanelControl
            or TerminalPanelControl;
    }

    /// <summary>
    /// Entfernt das Panel aus seinem Eltern-Element. Bei generischen
    /// Sektionen wird ein Platzhalter eingesetzt, bei den typisierten
    /// CodeWorkspace-Panels nicht, weil diese über CodeWorkspacePage.DockPanel
    /// an ihren Ursprung zurückkommen.
    /// </summary>
    private static void RemoveFromCurrentParent(IDraggablePanel panel, bool createPlaceholder)
    {
        var root = panel.DragRoot;
        var parent = root.Parent as DependencyObject;
        if (parent is null)
        {
            return;
        }

        int index = -1;
        int row = 0;
        int column = 0;

        if (parent is Panel panelParent)
        {
            index = panelParent.Children.IndexOf(root);
            row = (int)root.GetValue(Grid.RowProperty);
            column = (int)root.GetValue(Grid.ColumnProperty);
            _ = panelParent.Children.Remove(root);
        }
        else if (parent is ContentControl cc)
        {
            cc.Content = null;
        }
        else if (parent is Border border)
        {
            border.Child = null;
        }

        if (!createPlaceholder || index < 0)
        {
            return;
        }

        var placeholder = new Border
        {
            Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Transparent),
            MinHeight = root.ActualHeight,
            MinWidth = root.ActualWidth,
        };

        DraggableInfo.SetOriginalParent(placeholder, parent);
        DraggableInfo.SetOriginalIndex(placeholder, index);
        DraggableInfo.SetOriginalRow(placeholder, row);
        DraggableInfo.SetOriginalColumn(placeholder, column);

        panel.Placeholder = placeholder;

        if (parent is Panel pp)
        {
            pp.Children.Insert(index, placeholder);
        }
    }

    private static void RestoreFromPlaceholder(IDraggablePanel panel)
    {
        var root = panel.DragRoot;
        var placeholder = panel.Placeholder;
        if (placeholder is null)
        {
            return;
        }

        var parent = DraggableInfo.GetOriginalParent(placeholder) ?? placeholder.Parent;
        if (parent is Panel panelParent)
        {
            int index = DraggableInfo.GetOriginalIndex(placeholder);
            if (index < 0 || index > panelParent.Children.Count)
            {
                index = panelParent.Children.IndexOf(placeholder);
            }

            if (index >= 0)
            {
                _ = panelParent.Children.Remove(placeholder);
                panelParent.Children.Insert(index, root);
                root.SetValue(Grid.RowProperty, DraggableInfo.GetOriginalRow(placeholder));
                root.SetValue(Grid.ColumnProperty, DraggableInfo.GetOriginalColumn(placeholder));
            }
        }
        else if (parent is ContentControl cc)
        {
            cc.Content = root;
        }
        else if (parent is Border border)
        {
            border.Child = root;
        }

        panel.Placeholder = null;
    }

    private static IDraggablePanel? FindDraggablePanel(string panelId, int sourceWindowIndex)
    {
        var window = WindowStateCoordinator.GetWindowByIndex(sourceWindowIndex);
        if (window is null)
        {
            return null;
        }

        var root = window.Content as UIElement;
        if (root is null)
        {
            return null;
        }

        return FindDraggablePanelInTree(root, panelId);
    }

    private static IDraggablePanel? FindDraggablePanelInTree(UIElement root, string panelId)
    {
        if (root is IDraggablePanel draggable && draggable.PanelId == panelId)
        {
            return draggable;
        }

        int count = VisualTreeHelper.GetChildrenCount(root);
        for (int i = 0; i < count; i++)
        {
            var child = VisualTreeHelper.GetChild(root, i) as UIElement;
            if (child is not null)
            {
                var found = FindDraggablePanelInTree(child, panelId);
                if (found is not null)
                {
                    return found;
                }
            }
        }

        return null;
    }

    private static MultiScreenLayoutModel GetCurrentLayout()
    {
        string? profile = _viewModel?.Settings.ActiveLayoutProfile;
        return LayoutStore.Load(profile);
    }

    private static void SaveLayoutSnapshot(string panelId, int windowIndex, RectModel? bounds = null)
    {
        try
        {
            var layout = GetCurrentLayout();
            var existing = layout.Panels.FirstOrDefault(p => p.PanelId == panelId);
            if (existing is null)
            {
                layout.Panels.Add(new Models.PanelLayoutModel
                {
                    PanelId = panelId,
                    WindowIndex = windowIndex,
                    Bounds = bounds ?? new(),
                });
            }
            else
            {
                existing.WindowIndex = windowIndex;
                if (bounds is not null)
                {
                    existing.Bounds = bounds;
                }
            }
            LayoutStore.Save(layout, _viewModel?.Settings.ActiveLayoutProfile);
        }
        catch
        {
            // Best-effort.
        }
    }
}
