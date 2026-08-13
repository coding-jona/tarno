using System;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace TARNO.UI.MultiScreen;

public sealed partial class ContextDockWindow : Window
{
    private MainViewModel? _viewModel;

    public ContextDockWindow(MainViewModel viewModel)
    {
        this.InitializeComponent();
        _viewModel = viewModel;
        Title = "TARNO - Kontext";
        this.SystemBackdrop = new DesktopAcrylicBackdrop();
        WindowStateCoordinator.Register(this, fixedIndex: 2);
        Closed += OnWindowClosed;
        ContextDockPanel.AttachViewModel(viewModel);
        ContextDockPanel.WindowIndex = 2;
        ContextDockPanel.ClearContextRequested += (_, _) => viewModel.SelectedContextFiles.Clear();
        ContextDockPanel.CommandPaletteRequested += OnCommandPaletteRequested;
    }

    private async void OnCommandPaletteRequested(object? sender, System.EventArgs e)
    {
        // Befehlspalette ist ein Feature des Code-Workspaces; im separaten
        // Kontext-Fenster zeigen wir einen Hinweis an.
        var dialog = new ContentDialog
        {
            Title = "Befehlspalette",
            Content = "Die Befehlspalette ist im Hauptfenster im Code-Modus verfuegbar.",
            CloseButtonText = "OK",
            XamlRoot = Content?.XamlRoot,
        };
        _ = await dialog.ShowAsync();
    }

    private void OnWindowClosed(object sender, WindowEventArgs args)
    {
        WindowStateCoordinator.Unregister(this);
        if (ContextDockPanel is not null)
        {
            ContextDockPanel.CommandPaletteRequested -= OnCommandPaletteRequested;
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
        PanelDragService.HandleDropAsync(2, e);
    }
}
