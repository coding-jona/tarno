using TARNO.UI.ViewModels;
using TARNO.UI.Services;
using TARNO.UI.Models;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Windows.ApplicationModel.DataTransfer;
using System;

namespace TARNO.UI.UserControls;

/// <summary>
/// Kontext-Dock-Panel (markierte Dateien, Quick Actions, Provider/Modell,
/// Agent-Status). Löst Request-Events aus, die der Host-Page oder ein
/// separates Fenster implementiert - so ist das Panel sowohl inline als auch
/// in einem Extra-Fenster verwendbar.
/// </summary>
public sealed partial class ContextDockPanelControl : UserControl, IDraggablePanel
{
    public MainViewModel? ViewModel { get; private set; }

    public string PanelId => "context";
    public string Title => "Kontext";
    public int WindowIndex { get; set; }

    public FrameworkElement DragRoot => this;

    public FrameworkElement? Placeholder { get; set; }

    public ContextDockPanelControl()
    {
        this.InitializeComponent();
    }

    public void AttachViewModel(MainViewModel viewModel)
    {
        ViewModel = viewModel;
        Bindings.Update();
    }

    /// <summary>Wird ausgelöst, wenn der Nutzer die Befehlspalette öffnen möchte.</summary>
    public event EventHandler? CommandPaletteRequested;

    /// <summary>Wird ausgelöst, wenn der Nutzer den Dateikontext leeren möchte.</summary>
    public event EventHandler? ClearContextRequested;

    private void OnCommandPaletteClick(object sender, RoutedEventArgs e)
    {
        CommandPaletteRequested?.Invoke(this, EventArgs.Empty);
    }

    private void OnClearContextClick(object sender, RoutedEventArgs e)
    {
        ClearContextRequested?.Invoke(this, EventArgs.Empty);
    }

    public async void OnPanelDragStarting(UIElement sender, DragStartingEventArgs e)
    {
        e.AllowedOperations = DataPackageOperation.Move;
        await DragVisualService.SetDragVisualAsync(e, this);
        PanelDragService.SetDragPayload(e.Data, this);
    }
}
