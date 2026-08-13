using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using TARNO.UI.Controls;
using TARNO.UI.Models;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;

namespace TARNO.UI.MultiScreen;

/// <summary>
/// Generisches Floating-Fenster fuer ein einzelnes Panel.
/// Wird von der Docking-Logik (Phase 14) erzeugt, wenn ein Panel aus dem
/// Hauptlayout herausgezogen und auf einem beliebigen Bildschirm frei
/// platziert werden soll.
/// </summary>
public sealed partial class PanelWindow : Window
{
    public int WindowIndex { get; }
    public string? PanelId { get; private set; }

    public PanelWindow(MainViewModel viewModel)
    {
        this.InitializeComponent();
        ViewModel = viewModel;
        WindowIndex = WindowStateCoordinator.Register(this);
        Title = "TARNO - Panel";
        this.SystemBackdrop = new Microsoft.UI.Xaml.Media.DesktopAcrylicBackdrop();
        Closed += OnWindowClosed;

        try
        {
            AppWindow.Changed += OnAppWindowChanged;
        }
        catch
        {
            // Best-effort: nicht alle Window-Hosts unterstützen das Event.
        }
    }

    public MainViewModel ViewModel { get; }

    public void Host(UIElement? content) => Host(content, null);

    public void Host(UIElement? content, string? panelId)
    {
        PanelId = panelId ?? PanelId;

        if (content is FrameworkElement fe)
        {
            fe.DataContext = ViewModel;
        }

        if (PanelCanvas is null || content is null)
        {
            return;
        }

        if (!PanelCanvas.Children.Contains(content))
        {
            PanelCanvas.Children.Add(content);
            SetInitialGridSize(content);
        }

        PanelCanvas.SizeChanged += OnPanelCanvasSizeChanged;
    }

    public void Clear()
    {
        if (PanelCanvas is not null)
        {
            PanelCanvas.SizeChanged -= OnPanelCanvasSizeChanged;
            PanelCanvas.Children.Clear();
        }
    }

    private void SetInitialGridSize(UIElement content)
    {
        if (content is not FrameworkElement element || PanelCanvas is null)
        {
            return;
        }

        if (content is IPegboardPanel pegboard)
        {
            int columns = Math.Max(1, (int)(element.ActualWidth / PanelCanvas.GridSize));
            int rows = Math.Max(1, (int)(element.ActualHeight / PanelCanvas.GridSize));
            SnapCanvas.SetGridX(element, 0);
            SnapCanvas.SetGridY(element, 0);
            SnapCanvas.SetGridColumns(element, columns);
            SnapCanvas.SetGridRows(element, rows);
            pegboard.Scale = 1.0;
        }

        PanelCanvas.InvalidateMeasure();
    }

    private void OnPanelCanvasSizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (PanelCanvas is null || PanelCanvas.Children.Count != 1)
        {
            return;
        }

        var child = PanelCanvas.Children[0];
        if (child is not FrameworkElement element || child is not IPegboardPanel)
        {
            return;
        }

        int columns = Math.Max(1, (int)(PanelCanvas.ActualWidth / PanelCanvas.GridSize));
        int rows = Math.Max(1, (int)(PanelCanvas.ActualHeight / PanelCanvas.GridSize));
        SnapCanvas.SetGridColumns(element, columns);
        SnapCanvas.SetGridRows(element, rows);
        PanelCanvas.InvalidateMeasure();
    }

    private void OnWindowClosed(object sender, WindowEventArgs args)
    {
        try
        {
            AppWindow.Changed -= OnAppWindowChanged;
        }
        catch
        {
            // Best-effort.
        }
        WindowStateCoordinator.Unregister(this);
        Clear();
    }

    private void OnAppWindowChanged(Microsoft.UI.Windowing.AppWindow sender, Microsoft.UI.Windowing.AppWindowChangedEventArgs args)
    {
        if (string.IsNullOrEmpty(PanelId))
        {
            return;
        }

        if (args.DidPositionChange || args.DidSizeChange)
        {
            var rect = new RectModel
            {
                X = sender.Position.X,
                Y = sender.Position.Y,
                Width = (int)sender.Size.Width,
                Height = (int)sender.Size.Height,
            };
            DockingService.SavePanelBounds(PanelId, WindowIndex, rect);
        }
    }

    private void OnRootDragOver(object sender, DragEventArgs e)
    {
        PanelDragService.AcceptDrop(e);
        DropTargetOverlay.Visibility = Visibility.Visible;
    }

    private void OnRootDragLeave(object sender, DragEventArgs e)
    {
        DropTargetOverlay.Visibility = Visibility.Collapsed;
    }

    private void OnRootDrop(object sender, DragEventArgs e)
    {
        DropTargetOverlay.Visibility = Visibility.Collapsed;
        PanelDragService.HandleDropAsync(WindowIndex, e);
    }
}
