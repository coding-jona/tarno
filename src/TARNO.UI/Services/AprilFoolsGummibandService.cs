using System;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using TARNO.UI.Models;
using Windows.Graphics;

namespace TARNO.UI.Services;

/// <summary>
/// Überwacht die Fensterposition und zieht das Fenster langsam auf den Hauptmonitor zurück,
/// wenn es auf einen Sekundärmonitor gezogen wurde.
/// </summary>
public class AprilFoolsGummibandService
{
    private readonly Window _window;
    private readonly AppWindow _appWindow;
    private readonly AprilFoolsConfig _config;
    private readonly DispatcherQueueTimer? _timer;
    private readonly double _rasterizationScale;
    private bool _isDraggingBack;

    public AprilFoolsGummibandService(Window window, AprilFoolsConfig config)
    {
        _window = window;
        _appWindow = window.AppWindow;
        _config = config;
        _rasterizationScale = window.Content?.XamlRoot?.RasterizationScale ?? 1.0;

        _timer = window.DispatcherQueue?.CreateTimer();
        if (_timer is not null)
        {
            _timer.Interval = TimeSpan.FromMilliseconds(config.GummibandMsPerStep);
            _timer.Tick += OnTimerTick;
        }

        _appWindow.Changed += OnAppWindowChanged;
    }

    /// <summary>
    /// Stoppt Timer und Event-Abonnements.
    /// </summary>
    public void Detach()
    {
        if (_timer is not null)
        {
            _timer.Tick -= OnTimerTick;
            _timer.Stop();
        }

        try
        {
            _appWindow.Changed -= OnAppWindowChanged;
        }
        catch
        {
            // Best-effort.
        }
    }

    private void OnAppWindowChanged(AppWindow sender, AppWindowChangedEventArgs args)
    {
        if (!args.DidPositionChange || _isDraggingBack)
        {
            return;
        }

        if (IsOnSecondaryMonitor())
        {
            AprilFoolsAudioService.Play(AprilFoolsOrchestrator.Locale?.MonitorDrag?.Audio ?? "monitor_drag.wav");
            _timer?.Start();
        }
    }

    private bool IsOnSecondaryMonitor()
    {
        try
        {
            var current = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(_appWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.None);
            if (current is null)
            {
                return false;
            }

            // Primär wenn WorkArea an (0,0) beginnt.
            return current.WorkArea.X != 0 || current.WorkArea.Y != 0;
        }
        catch
        {
            return false;
        }
    }

    private void OnTimerTick(DispatcherQueueTimer timer, object args)
    {
        try
        {
            var primary = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(_appWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Primary);
            if (primary is null)
            {
                _timer?.Stop();
                return;
            }

            var workArea = primary.WorkArea;
            var currentPos = _appWindow.Position;
            var scale = _rasterizationScale;

            // Ziel in logischen DIPs, da AppWindow-APIs physische Pixel erwarten.
            int targetX = workArea.X + 50;
            int targetY = workArea.Y + 50;

            int deltaX = targetX - currentPos.X;
            int deltaY = targetY - currentPos.Y;
            double distance = Math.Sqrt(deltaX * deltaX + deltaY * deltaY);

            if (distance < _config.GummibandStepDip * scale)
            {
                _appWindow.Move(new PointInt32(targetX, targetY));
                _timer?.Stop();
                _isDraggingBack = false;
                return;
            }

            _isDraggingBack = true;

            double stepX = (deltaX / distance) * _config.GummibandStepDip * scale;
            double stepY = (deltaY / distance) * _config.GummibandStepDip * scale;

            int newX = (int)(currentPos.X + stepX);
            int newY = (int)(currentPos.Y + stepY);

            _appWindow.Move(new PointInt32(newX, newY));
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Gummiband-Zug fehlgeschlagen: {ex.Message}");
            _timer?.Stop();
            _isDraggingBack = false;
        }
    }
}
