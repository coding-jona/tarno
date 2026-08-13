using TARNO.UI.Dialogs;
using TARNO.UI.Pages;
using TARNO.UI.Services;
using TARNO.UI.UserControls;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Animation;
using Microsoft.UI.Xaml.Navigation;
using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Windows.UI;

namespace TARNO.UI;

public sealed partial class MainWindow : Window
{
    public MainViewModel ViewModel { get; } = new MainViewModel();

    // The backend's single-worker executor only ever runs one command at a
    // time, so at most one PermissionRequest should be in flight - this
    // just guards against ShowAsync being called twice concurrently on the
    // same XamlRoot (which WinUI does not allow) if that assumption ever
    // stops holding (e.g. future parallel tool calls).
    private readonly SemaphoreSlim _permissionDialogGate = new(1, 1);

    private const double SidebarExpandedWidth = 240;
    private const double SidebarCollapsedWidth = 0;
    private bool _sidebarCollapsed;

    public MainWindow()
    {
        this.InitializeComponent();
        // Diese Kopie ist bewusst als "TARNO Mesh" gebrandet - eigene
        // Fork-Identitaet fuer die Dynamic-Hybrid-Mesh-Integration, getrennt
        // vom Original. Interne Speicherordner (%LOCALAPPDATA%\TARNO\...)
        // bleiben unveraendert, um bestehende Einstellungen/Logs/Chats aus
        // fruaeheren Laeufen nicht zu verwaisen.
        Title = "TARNO Mesh";
        _ = WindowStateCoordinator.Register(this, isMain: true);
        DockingService.Initialize(ViewModel);
        LanguageCombo.SelectedIndex = ViewModel.Settings.Language == "en" ? 1 : 0;
        SetWindowIcon();
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1280, 800));
        ViewModel.SetDispatcher(this.DispatcherQueue);
        ViewModel.PropertyChanged += ViewModel_PropertyChanged;

        TryActivateAprilFools();
        ViewModel.Connected += OnFirstConnected;
        ViewModel.PermissionRequested += OnPermissionRequested;
        UpdateNavSelection();
        NavigateTo(ViewModel.SelectedPage);

        _sidebarCollapsed = SidebarStateStore.LoadCollapsed();
        SidebarRoot.Width = _sidebarCollapsed ? SidebarCollapsedWidth : SidebarExpandedWidth;

        LayoutDiagnosticsService.TestMultiScreenDetection();
    }

    private void OnToggleSidebarClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MainWindow", "SidebarToggleButton");
        try
        {
            _sidebarCollapsed = !_sidebarCollapsed;
            double from = SidebarRoot.Width;
            double to = _sidebarCollapsed ? SidebarCollapsedWidth : SidebarExpandedWidth;

            // EnableDependentAnimation=true ist zwingend: Width/Height sind
            // "layout-abhaengige" Eigenschaften, deren Animation WinUI/UWP
            // standardmaessig stillschweigend UNTERDRUECKT (kein Fehler, die
            // Animation laeuft einfach nicht) - der wahrscheinlichste Grund,
            // warum der Button vorher wirkungslos wirkte.
            var animation = new DoubleAnimation
            {
                From = from,
                To = to,
                Duration = new Duration(TimeSpan.FromMilliseconds(280)),
                EasingFunction = new QuinticEase { EasingMode = _sidebarCollapsed ? EasingMode.EaseIn : EasingMode.EaseOut },
                EnableDependentAnimation = true,
            };
            Storyboard.SetTarget(animation, SidebarRoot);
            Storyboard.SetTargetProperty(animation, "Width");

            var storyboard = new Storyboard();
            storyboard.Children.Add(animation);
            storyboard.Begin();

            SidebarStateStore.SaveCollapsed(_sidebarCollapsed);
            InteractionLogger.Info("MainWindow", $"SidebarToggle abgeschlossen: {(_sidebarCollapsed ? "Collapsed" : "Expanded")} ({from}->{to})");
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("MainWindow", $"SidebarToggle-Exception: {ex}");
        }
    }

    private void TryActivateAprilFools()
    {
        try
        {
            if (AprilFoolsOrchestrator.TryActivate(this))
            {
                DefaultTitleBar.Visibility = Visibility.Collapsed;
                AprilFoolsTitleBarRow.Height = new GridLength(46);
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Aktivierung fehlgeschlagen: {ex.Message}");
        }
    }

    private void SetWindowIcon()
    {
        try
        {
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            var windowId = Microsoft.UI.Win32Interop.GetWindowIdFromWindow(hwnd);
            var appWindow = Microsoft.UI.Windowing.AppWindow.GetFromWindowId(windowId);
            
            // Set the icon from the assets folder
            string iconPath = System.IO.Path.Combine(AppContext.BaseDirectory, "Assets", "app.ico");
            if (System.IO.File.Exists(iconPath))
            {
                appWindow.SetIcon(iconPath);
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Fehler beim Setzen des App-Icons: {ex.Message}");
        }
    }

    private void OnRunLayoutDiagnostics(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args)
    {
        LayoutDiagnosticsService.TestMultiScreenDetection();
        LayoutDiagnosticsService.ValidateAllWindows();
        args.Handled = true;
    }

    private async void OnPermissionRequested(string requestId, string permission, string target, string riskLevel, string safetyPhrase)
    {
        await _permissionDialogGate.WaitAsync();
        try
        {
            var dialog = new Dialogs.PermissionDialog(permission, target, riskLevel, safetyPhrase)
            {
                XamlRoot = this.Content.XamlRoot,
            };
            var result = await dialog.ShowAsync();
            bool approved = result == ContentDialogResult.Primary;
            await ViewModel.SendPermissionResponseAsync(requestId, approved, approved && dialog.Persistent);
        }
        catch (Exception ex)
        {
            // async void: an uncaught exception here would crash the whole app.
            // Deny by default so a broken dialog can't leave a HIGH-risk
            // command silently unanswered.
            InteractionLogger.Error("PERMISSION", $"Permission-Dialog fehlgeschlagen: {ex.Message}");
            try
            {
                await ViewModel.SendPermissionResponseAsync(requestId, false, false);
            }
            catch (Exception)
            {
                // Backend unreachable too - nothing more we can do here.
            }
        }
        finally
        {
            _permissionDialogGate.Release();
        }
    }

    private async void OnFirstConnected()
    {
        ViewModel.Connected -= OnFirstConnected;

        if (ViewModel.Settings.FirstRunWizardCompleted)
        {
            return;
        }

        bool anyConfigured;
        try
        {
            var status = await ViewModel.GetApiKeyStatusAsync();
            anyConfigured = status.Values.Any(configured => configured);
        }
        catch (Exception)
        {
            // Backend/Vault nicht erreichbar - Wizard beim naechsten Start erneut versuchen.
            return;
        }

        try
        {
            if (!anyConfigured)
            {
                var dialog = new FirstStartWizardDialog(ViewModel) { XamlRoot = this.Content.XamlRoot };
                await dialog.ShowAsync();
            }

            ViewModel.Settings.FirstRunWizardCompleted = true;
            SettingsStore.Save(ViewModel.Settings);
        }
        catch (Exception ex)
        {
            // async void: an uncaught exception here would crash the whole app.
            InteractionLogger.Error("FIRSTSTART", $"First-Start-Wizard fehlgeschlagen: {ex.Message}");
        }
    }

    private void ViewModel_PropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(ViewModel.SelectedPage))
        {
            UpdateNavSelection();
            NavigateTo(ViewModel.SelectedPage);
        }
    }

    private void NavigateTo(AppPage page)
    {
        Type? pageType = page switch
        {
            AppPage.Home => typeof(HomePage),
            AppPage.Voice => typeof(VoicePage),
            AppPage.Chat => typeof(ChatPage),
            AppPage.Tasks => typeof(TasksPage),
            AppPage.Memory => typeof(MemoryPage),
            AppPage.Settings => typeof(SettingsPage),
            AppPage.ApiKeys => typeof(ApiKeysPage),
            AppPage.Logs => typeof(LogsPage),
            AppPage.Workspaces => typeof(WorkspacesPage),
            AppPage.Code => typeof(CodeWorkspacePage),
            AppPage.MeshDevices => typeof(MeshDevicesPage),
            AppPage.MeshDashboard => typeof(MeshDashboardPage),
            _ => typeof(HomePage),
        };

        if (ContentFrame.CurrentSourcePageType != pageType)
        {
            ContentFrame.Navigate(pageType, ViewModel);
        }
    }

    private void OnNavClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && AprilFoolsOrchestrator.TryInterceptMainButton(button))
        {
            return;
        }

        if (sender is Button { Tag: string tag })
        {
            InteractionLogger.Click("MainWindow", $"Nav{tag}");
            if (Enum.TryParse<AppPage>(tag, out var page))
            {
                var previous = ViewModel.SelectedPage;
                ViewModel.SelectPage(page);
                InteractionLogger.Navigate(previous.ToString(), page.ToString());
            }
        }
    }

    private void OnModeChatClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && AprilFoolsOrchestrator.TryInterceptMainButton(button))
        {
            return;
        }

        ViewModel.SelectedSidebarMode = SidebarMode.Chat;
        UpdateSidebarMode();
    }

    private void OnModeCodeClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && AprilFoolsOrchestrator.TryInterceptMainButton(button))
        {
            return;
        }

        ViewModel.SelectedSidebarMode = SidebarMode.Code;
        UpdateSidebarMode();
        ViewModel.SelectPage(ViewModel.SelectedWorkspace is null ? AppPage.Workspaces : AppPage.Code);
    }

    private void UpdateSidebarMode()
    {
        bool isCode = ViewModel.SelectedSidebarMode == SidebarMode.Code;
        // StandardNavPanel wurde in einen ScrollViewer gewickelt (siehe
        // MainWindow.xaml, "Mesh-Geräte"-Nav-Punkt), Visibility muss deshalb
        // am ScrollViewer-Wrapper umgeschaltet werden, nicht mehr am
        // StackPanel selbst - sonst bliebe der (jetzt leere) ScrollViewer
        // sichtbar, wenn eigentlich der Code-Modus aktiv ist.
        StandardNavScrollViewer.Visibility = isCode ? Visibility.Collapsed : Visibility.Visible;
        WorkspaceNavPanel.Visibility = isCode ? Visibility.Visible : Visibility.Collapsed;
    }

    private void OnWorkspaceSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (WorkspaceListView.SelectedItem is Models.Workspace workspace)
        {
            ViewModel.SelectedWorkspace = workspace;
            ViewModel.SelectPage(AppPage.Code);
        }
    }

    private void OnManageWorkspacesClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && AprilFoolsOrchestrator.TryInterceptMainButton(button))
        {
            return;
        }

        ViewModel.SelectPage(AppPage.Workspaces);
    }

    private void OnNewChatClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && AprilFoolsOrchestrator.TryInterceptMainButton(button))
        {
            return;
        }

        if (ViewModel.SelectedSidebarMode == SidebarMode.Code && ViewModel.SelectedWorkspace is not null)
        {
            ViewModel.NewChatForWorkspace(ViewModel.SelectedWorkspace.Id);
        }
        else
        {
            ViewModel.NewChat();
        }
        ViewModel.SelectPage(ViewModel.SelectedSidebarMode == SidebarMode.Code ? AppPage.Code : AppPage.Chat);
    }

    private async void OnLanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (LanguageCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            if (ViewModel.Settings.Language == tag)
            {
                return;
            }
            await ViewModel.SetLanguageAsync(tag);

            var isEn = tag == "en";
            var dialog = new ContentDialog
            {
                XamlRoot = this.Content.XamlRoot,
                Title = isEn ? "Language changed" : "Sprache geändert",
                Content = isEn
                    ? "The UI language will be applied after you restart TARNO."
                    : "Die Sprache der Oberfläche wird nach einem Neustart übernommen.",
                PrimaryButtonText = isEn ? "OK" : "OK",
                DefaultButton = ContentDialogButton.Primary,
            };
            _ = dialog.ShowAsync();
        }
    }

    private void OnChatSessionSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ViewModel is null || ChatSessionsListView.SelectedItem is not ViewModels.ChatSessionViewModel session)
        {
            return;
        }
        ViewModel.SelectChatSession(session.Id);
        var targetPage = ViewModel.SelectedSidebarMode == SidebarMode.Code ? AppPage.Code : AppPage.Chat;
        if (ViewModel.SelectedPage != targetPage)
        {
            ViewModel.SelectPage(targetPage);
        }
    }

    private void OnDeleteChatClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.Tag is string id)
        {
            ViewModel.DeleteChatSession(id);
        }
    }

    private void UpdateNavSelection()
    {
        // Selected item is its own small Liquid-Glass card (AcrylicBrush +
        // edge highlight), not just a flat accent-colored fill — matches
        // the reference artifact's individual "floating" glass boxes
        // rather than one flat panel colored per state.
        var selectedBrush = (AcrylicBrush)Application.Current.Resources["LiquidGlassStrongBrush"];
        var selectedEdgeBrush = (LinearGradientBrush)Application.Current.Resources["LiquidGlassEdgeStrongBrush"];
        var transparentBrush = new SolidColorBrush(Color.FromArgb(0, 0, 0, 0));

        void SetBg(Button button, bool selected)
        {
            button.Background = selected ? selectedBrush : transparentBrush;
            button.BorderBrush = selected ? selectedEdgeBrush : transparentBrush;
            button.BorderThickness = selected ? new Thickness(1) : new Thickness(0);
        }

        SetBg(NavHome, ViewModel.SelectedPage == AppPage.Home);
        SetBg(NavVoice, ViewModel.SelectedPage == AppPage.Voice);
        SetBg(NavChat, ViewModel.SelectedPage == AppPage.Chat);
        SetBg(NavTasks, ViewModel.SelectedPage == AppPage.Tasks);
        SetBg(NavMemory, ViewModel.SelectedPage == AppPage.Memory);
        SetBg(NavSettings, ViewModel.SelectedPage == AppPage.Settings);
        SetBg(NavApiKeys, ViewModel.SelectedPage == AppPage.ApiKeys);
        SetBg(NavLogs, ViewModel.SelectedPage == AppPage.Logs);
        SetBg(NavMeshDevices, ViewModel.SelectedPage == AppPage.MeshDevices);
        SetBg(NavMeshDashboard, ViewModel.SelectedPage == AppPage.MeshDashboard);
    }

    private void OnContentFrameNavigated(object sender, NavigationEventArgs e)
    {
        // Optional: animate page transitions or update breadcrumbs here.
    }
}
