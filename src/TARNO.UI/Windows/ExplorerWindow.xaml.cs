using TARNO.UI.Services;
using TARNO.UI.UserControls;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Media;

namespace TARNO.UI.MultiScreen;

public sealed partial class ExplorerWindow : Window
{
    public ExplorerWindow(MainViewModel viewModel)
    {
        this.InitializeComponent();
        Title = "TARNO - Explorer";
        this.SystemBackdrop = new DesktopAcrylicBackdrop();
        WindowStateCoordinator.Register(this, fixedIndex: 1);
        Closed += OnWindowClosed;
        ExplorerPanel.AttachViewModel(viewModel);
        ExplorerPanel.WindowIndex = 1;
    }

    private void OnWindowClosed(object sender, WindowEventArgs args)
    {
        WindowStateCoordinator.Unregister(this);
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
        PanelDragService.HandleDropAsync(1, e);
    }

    public ExplorerPanelControl ExplorerControl => ExplorerPanel;
}
