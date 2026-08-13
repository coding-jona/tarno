using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using TARNO.UI.Models;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Windows.ApplicationModel.DataTransfer;
using System;

namespace TARNO.UI.UserControls;

public sealed partial class TerminalPanelControl : UserControl, IDraggablePanel
{
    public MainViewModel? ViewModel { get; private set; }
    public TerminalService? Terminal { get; private set; }

    public string PanelId => "terminal";
    public string Title => "Terminal";
    public int WindowIndex { get; set; }

    public FrameworkElement DragRoot => this;

    public FrameworkElement? Placeholder { get; set; }

    public TerminalPanelControl()
    {
        this.InitializeComponent();
    }

    public void AttachViewModel(MainViewModel viewModel)
    {
        ViewModel = viewModel;
        Bindings.Update();
    }

    public void AttachTerminal(TerminalService terminal)
    {
        Terminal = terminal;
        Bindings.Update();
    }

    /// <summary>Wird ausgelöst, wenn das Terminal ein- oder ausgeklappt wird.</summary>
    public event EventHandler<TerminalToggledEventArgs>? TerminalToggled;

    public bool IsTerminalCollapsed { get; private set; }

    private void OnTerminalInputKeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter)
        {
            SendTerminalCommand();
            e.Handled = true;
        }
    }

    private void SendTerminalCommand()
    {
        var command = TerminalInput.Text;
        if (string.IsNullOrWhiteSpace(command) || Terminal is null)
        {
            return;
        }
        Terminal.SendInput(command);
        TerminalInput.Text = string.Empty;
    }

    private void OnTerminalPanelToggleClick(object sender, RoutedEventArgs e)
    {
        bool collapse = TerminalContent.Visibility == Visibility.Visible;
        var contentVisibility = collapse ? Visibility.Collapsed : Visibility.Visible;
        TerminalContent.Visibility = contentVisibility;
        TerminalToggleButton.Content = collapse ? "▶" : "▼";
        IsTerminalCollapsed = collapse;
        TerminalToggled?.Invoke(this, new TerminalToggledEventArgs(!collapse));
    }

    public async void OnPanelDragStarting(UIElement sender, DragStartingEventArgs e)
    {
        e.AllowedOperations = DataPackageOperation.Move;
        await DragVisualService.SetDragVisualAsync(e, this);
        PanelDragService.SetDragPayload(e.Data, this);
    }

    private void OnPanelHeaderDoubleTapped(object sender, Microsoft.UI.Xaml.Input.DoubleTappedRoutedEventArgs e)
    {
        DockingService.UndockToNewWindow(this);
    }
}

public sealed class TerminalToggledEventArgs : EventArgs
{
    public bool IsExpanded { get; }

    public TerminalToggledEventArgs(bool isExpanded)
    {
        IsExpanded = isExpanded;
    }
}
