using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Windowing;
using TARNO.UI.Models;
using TARNO.UI.ViewModels;
using Windows.Graphics;
using Windows.System;

namespace TARNO.UI.Services;

/// <summary>
/// Zentraler Koordinator für den April-Fools-Modus.
/// Aktiviert/Deaktiviert Frameless-Window, Custom-Titlebar,
/// Audio-Overrides, Gummiband und ausweichenden X-Button.
/// </summary>
public static class AprilFoolsOrchestrator
{
    public static bool IsActive { get; private set; }
    public static AprilFoolsConfig? Config { get; private set; }
    public static AprilFoolsLocale? Locale { get; private set; }
    public static bool IsCustomClose { get; set; }
    public static bool IsAltF4Close { get; set; }

    private static MainWindow? _mainWindow;
    private static Border? _titleBar;
    private static Canvas? _overlay;
    private static Button? _closeButton;
    private static AprilFoolsCloseButtonService? _closeButtonService;
    private static AprilFoolsGummibandService? _gummibandService;

    private static readonly List<long> _enterPressTimes = new();
    private static PointInt32 _dragStartWindowPos;
    private static Windows.Foundation.Point _dragStartPointerPos;
    private static bool _isDraggingWindow;
    private static double _rasterizationScale = 1.0;

    /// <summary>
    /// Prüft, ob der Modus aktiv sein soll, und initialisiert ihn ggf.
    /// </summary>
    public static bool TryActivate(MainWindow window)
    {
        if (IsActive)
        {
            return true;
        }

        var settings = window.ViewModel.Settings;
        if (!AprilFoolsConfigService.IsAprilFoolsEnabled(settings))
        {
            return false;
        }

        Config = AprilFoolsConfigService.LoadConfig() ?? new AprilFoolsConfig();
        Locale = AprilFoolsConfigService.LoadLocale(Config.Locale) ?? new AprilFoolsLocale();

        if (string.IsNullOrEmpty(Config.AssetBasePath))
        {
            Config.AssetBasePath = "Assets/AprilFools";
        }

        AprilFoolsAudioService.Initialize(System.IO.Path.Combine(AppContext.BaseDirectory, Config.AssetBasePath));

        _mainWindow = window;
        _overlay = window.AprilFoolsOverlay;
        _closeButton = window.AprilFoolsCloseButton;
        _titleBar = window.AprilFoolsTitleBar;

        if (_overlay is null || _closeButton is null || _titleBar is null)
        {
            InteractionLogger.Warn("APRILFOOLS", "Overlay-Elemente nicht in MainWindow gefunden.");
            return false;
        }

        _rasterizationScale = window.Content?.XamlRoot?.RasterizationScale ?? 1.0;
        ConfigureWindowFrame(window);

        _titleBar.Visibility = Visibility.Visible;
        _overlay.Visibility = Visibility.Visible;
        _closeButton.Visibility = Visibility.Visible;

        _closeButtonService = new AprilFoolsCloseButtonService(window, _overlay, _closeButton, _titleBar, Config, Locale);
        _gummibandService = new AprilFoolsGummibandService(window, Config);

        AttachGlobalHooks(window);

        IsActive = true;
        InteractionLogger.Info("APRILFOOLS", "April-Fools-Modus aktiviert.");
        return true;
    }

    /// <summary>
    /// Deaktiviert den Modus und gibt Ressourcen frei.
    /// </summary>
    public static void Deactivate()
    {
        if (!IsActive)
        {
            return;
        }

        DetachGlobalHooks();
        _closeButtonService?.Detach();
        _closeButtonService = null;

        _gummibandService?.Detach();
        _gummibandService = null;

        _overlay?.Children.Clear();
        if (_overlay is not null)
        {
            _overlay.Visibility = Visibility.Collapsed;
        }

        IsActive = false;
        _mainWindow = null;
        _overlay = null;
        _closeButton = null;
        _titleBar = null;
        InteractionLogger.Info("APRILFOOLS", "April-Fools-Modus deaktiviert.");
    }

    /// <summary>
    /// Wird vom echten Schließen-Button aufgerufen.
    /// </summary>
    public static void RequestCustomClose()
    {
        IsCustomClose = true;
        _mainWindow?.Close();
    }

    private static void ConfigureWindowFrame(MainWindow window)
    {
        try
        {
            var appWindow = window.AppWindow;
            if (appWindow.Presenter is Microsoft.UI.Windowing.OverlappedPresenter presenter)
            {
                // Keine OS-Titlebar, aber ein dünner Border für Resize bleibt erhalten.
                presenter.SetBorderAndTitleBar(true, false);
            }

            // Eigene Titlebar-Erweiterung, damit SetDragRectangles greift.
            appWindow.TitleBar.ExtendsContentIntoTitleBar = true;
            appWindow.TitleBar.PreferredHeightOption = Microsoft.UI.Windowing.TitleBarHeightOption.Standard;
            appWindow.TitleBar.SetDragRectangles(new[]
            {
                new RectInt32(0, 0, (int)(appWindow.ClientSize.Width * _rasterizationScale), (int)(46 * _rasterizationScale)),
            });
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Fenster-Rahmenkonfiguration fehlgeschlagen: {ex.Message}");
        }
    }

    private static void AttachGlobalHooks(MainWindow window)
    {
        if (window.Content is UIElement root)
        {
            root.PreviewKeyDown += OnPreviewKeyDown;
        }

        if (_titleBar is not null)
        {
            _titleBar.PointerPressed += OnTitleBarPointerPressed;
            _titleBar.PointerMoved += OnTitleBarPointerMoved;
            _titleBar.PointerReleased += OnTitleBarPointerReleased;
        }

        window.Closed += OnWindowClosed;
        window.AppWindow.Closing += OnAppWindowClosing;
    }

    private static void DetachGlobalHooks()
    {
        if (_mainWindow?.Content is UIElement root)
        {
            root.PreviewKeyDown -= OnPreviewKeyDown;
        }

        if (_titleBar is not null)
        {
            _titleBar.PointerPressed -= OnTitleBarPointerPressed;
            _titleBar.PointerMoved -= OnTitleBarPointerMoved;
            _titleBar.PointerReleased -= OnTitleBarPointerReleased;
        }

        if (_mainWindow is not null)
        {
            _mainWindow.Closed -= OnWindowClosed;
            _mainWindow.AppWindow.Closing -= OnAppWindowClosing;
        }
    }

    private static void OnPreviewKeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key == VirtualKey.Enter)
        {
            TrackEnterPress();
        }

        if (e.Key == VirtualKey.F4)
        {
            var menuState = Microsoft.UI.Input.InputKeyboardSource.GetKeyStateForCurrentThread(VirtualKey.Menu);
            if (menuState.HasFlag(Windows.UI.Core.CoreVirtualKeyStates.Down))
            {
                IsAltF4Close = true;
            }
        }
    }

    private static void TrackEnterPress()
    {
        if (Config is null)
        {
            return;
        }

        var now = DateTimeOffset.Now;
        _enterPressTimes.Add(now.ToUnixTimeMilliseconds());

        long threshold = now.ToUnixTimeMilliseconds() - (Config.KeyboardStressMaxMsBetweenEnters * Config.KeyboardStressMinRepeatedEnters);
        _enterPressTimes.RemoveAll(t => t < threshold);

        int count = _enterPressTimes.Count;
        if (count >= Config.KeyboardStressMinRepeatedEnters)
        {
            _enterPressTimes.Clear();
            AprilFoolsAudioService.Play(Locale?.KeyboardStress?.Audio ?? "keyboard_stress.wav");
        }
    }

    /// <summary>
    /// Prüft, ob der April-Fools-Modus einen Haupt-Button-Klick abfangen soll.
    /// Gibt true zurück, wenn der Click nicht normal weiterverarbeitet werden soll.
    /// </summary>
    public static bool TryInterceptMainButton(Button? button)
    {
        if (!IsActive || button is null || Locale?.MainButtonClick is null)
        {
            return false;
        }

        string name = button.Name ?? string.Empty;
        // NavSettings ist bewusst ausgenommen (live gefundener Soft-Lock): OnNavClick
        // faengt ALLE Sidebar-Buttons ab, inklusive der Navigation zur Settings-Seite -
        // ohne diese Ausnahme gibt es aus der laufenden Sitzung heraus keinen Weg mehr
        // zurueck zum AprilFoolsSwitch, um den Modus wieder auszuschalten (der Prank
        // darf nie seinen eigenen Ausschalter blockieren).
        string[] ignored = { "AprilFoolsCloseButton", "NavSettings" };
        if (ignored.Contains(name) || name.StartsWith("AprilFoolsFake", StringComparison.Ordinal))
        {
            return false;
        }

        ShowToast(Locale.MainButtonClick.Toast);
        AprilFoolsAudioService.Play(Locale.MainButtonClick.Audio);
        return true;
    }

    private static void OnTitleBarPointerPressed(object sender, PointerRoutedEventArgs e)
    {
        if (_mainWindow is null)
        {
            return;
        }

        var point = e.GetCurrentPoint(_titleBar);
        if (point.Properties.IsLeftButtonPressed)
        {
            _isDraggingWindow = true;
            _dragStartWindowPos = _mainWindow.AppWindow.Position;
            _dragStartPointerPos = point.Position;
            _titleBar?.CapturePointer(e.Pointer);
            e.Handled = true;
        }
    }

    private static void OnTitleBarPointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!_isDraggingWindow || _mainWindow is null || _titleBar is null)
        {
            return;
        }

        var point = e.GetCurrentPoint(_titleBar);
        var delta = new Windows.Foundation.Point(
            point.Position.X - _dragStartPointerPos.X,
            point.Position.Y - _dragStartPointerPos.Y);

        int newX = (int)(_dragStartWindowPos.X + delta.X * _rasterizationScale);
        int newY = (int)(_dragStartWindowPos.Y + delta.Y * _rasterizationScale);

        _mainWindow.AppWindow.Move(new PointInt32(newX, newY));
    }

    private static void OnTitleBarPointerReleased(object sender, PointerRoutedEventArgs e)
    {
        _isDraggingWindow = false;
        _titleBar?.ReleasePointerCapture(e.Pointer);
    }

    private static void OnAppWindowClosing(AppWindow sender, AppWindowClosingEventArgs e)
    {
        if (IsCustomClose)
        {
            // Normal schließen, ohne Audio-Streik.
            return;
        }

        if (IsAltF4Close)
        {
            e.Cancel = true;
            PlayCloseAndExit(Locale?.ForceQuit?.Audio ?? "alt_f4_traitor.wav");
            return;
        }

        // Taskleisten-Schließen oder sonstiger Close-Request.
        e.Cancel = true;
        PlayCloseAndExit(Locale?.TaskbarClose?.Audio ?? "taskbar_respect.wav");
    }

    private static void PlayCloseAndExit(string audioFile)
    {
        if (_mainWindow is null)
        {
            return;
        }

        try
        {
            IsCustomClose = true;
            IsAltF4Close = false;
            AprilFoolsAudioService.Play(audioFile);
            _mainWindow.DispatcherQueue?.TryEnqueue(() =>
            {
                // Kurze Verzögerung, damit das Audio anfängt, dann schließen.
                var timer = _mainWindow?.DispatcherQueue?.CreateTimer();
                if (timer is not null)
                {
                    timer.Interval = TimeSpan.FromMilliseconds(1200);
                    timer.Tick += (t, args) =>
                    {
                        t.Stop();
                        _mainWindow?.Close();
                    };
                    timer.Start();
                }
            });
        }
        catch
        {
            _mainWindow?.Close();
        }
    }

    private static void OnWindowClosed(object sender, WindowEventArgs e)
    {
        Deactivate();
    }

    private static void ShowToast(string message)
    {
        // Einfacher InfoBar-Toast im MainWindow.
        if (_mainWindow?.Content is FrameworkElement root)
        {
            var info = new InfoBar
            {
                Message = message,
                IsOpen = true,
                Severity = InfoBarSeverity.Warning,
                HorizontalAlignment = Microsoft.UI.Xaml.HorizontalAlignment.Center,
                VerticalAlignment = Microsoft.UI.Xaml.VerticalAlignment.Top,
                Margin = new Thickness(0, 80, 0, 0),
                Width = 320,
            };

            if (root is Panel panel)
            {
                panel.Children.Add(info);
            }

            var timer = _mainWindow.DispatcherQueue?.CreateTimer();
            if (timer is not null)
            {
                timer.Interval = TimeSpan.FromSeconds(2.5);
                timer.Tick += (t, args) =>
                {
                    t.Stop();
                    if (root is Panel p)
                    {
                        p.Children.Remove(info);
                    }
                };
                timer.Start();
            }
        }
    }
}
