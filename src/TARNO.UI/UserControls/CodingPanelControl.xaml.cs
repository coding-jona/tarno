using TARNO.UI.ViewModels;
using TARNO.UI.Services;
using TARNO.UI.Models;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Windows.ApplicationModel.DataTransfer;
using System;
using System.Threading.Tasks;

namespace TARNO.UI.UserControls;

public sealed partial class CodingPanelControl : UserControl, IDraggablePanel
{
    public MainViewModel? ViewModel { get; private set; }

    public string PanelId => "coding";
    public string Title => "Coding";
    public int WindowIndex { get; set; }

    public FrameworkElement DragRoot => this;

    public FrameworkElement? Placeholder { get; set; }

    public CodingPanelControl()
    {
        this.InitializeComponent();
    }

    public void AttachViewModel(MainViewModel viewModel)
    {
        ViewModel = viewModel;
        Bindings.Update();
    }

    public void Expand()
    {
        CodingContent.Visibility = Visibility.Visible;
        CodingToggleButton.Content = "▼";
    }

    public void FocusInput()
    {
        _ = CodingInput.Focus(FocusState.Programmatic);
    }

    private void OnCodingInputKeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter)
        {
            _ = SendCodingTaskAsync();
            e.Handled = true;
        }
    }

    private async Task SendCodingTaskAsync()
    {
        var prompt = CodingInput.Text;
        if (string.IsNullOrWhiteSpace(prompt) || ViewModel is null)
        {
            return;
        }
        await ViewModel.SendCodingTaskAsync(prompt, Array.Empty<string>(), ReadOnlyCheck.IsChecked ?? false);
        CodingInput.Text = string.Empty;
    }

    private void OnSendCodingTaskClick(object sender, RoutedEventArgs e)
    {
        _ = SendCodingTaskAsync();
    }

    private void OnCodingPanelToggleClick(object sender, RoutedEventArgs e)
    {
        bool expand = CodingContent.Visibility == Visibility.Collapsed;
        CodingContent.Visibility = expand ? Visibility.Visible : Visibility.Collapsed;
        CodingToggleButton.Content = expand ? "▼" : "▶";
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
