using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Steuert den ausweichenden Schließen-Button in drei Eskalationsstufen
/// und spawnt in Stufe 3 Fake-X-Icons.
/// </summary>
public class AprilFoolsCloseButtonService
{
    private readonly Window _window;
    private readonly Canvas _overlay;
    private readonly Button _closeButton;
    private readonly Border? _titleBar;
    private readonly AprilFoolsConfig _config;
    private readonly AprilFoolsLocale _locale;
    private readonly Random _random = new();
    private readonly DispatcherQueue _dispatcher;

    private readonly List<Button> _fakeButtons = new();
    private int _evadeCount;
    private DateTime _lastEvade = DateTime.MinValue;
    private bool _stage3Active;
    private const double ButtonWidth = 46;
    private const double ButtonHeight = 46;
    private const double TitlebarHeight = 58;

    public AprilFoolsCloseButtonService(Window window, Canvas overlay, Button closeButton, Border? titleBar, AprilFoolsConfig config, AprilFoolsLocale locale)
    {
        _window = window;
        _overlay = overlay;
        _closeButton = closeButton;
        _titleBar = titleBar;
        _config = config;
        _locale = locale;
        _dispatcher = window.DispatcherQueue ?? DispatcherQueue.GetForCurrentThread();

        _closeButton.Click += OnCloseButtonClick;
        _overlay.SizeChanged += OnOverlaySizeChanged;

        if (window.Content is UIElement root)
        {
            root.PointerMoved += OnPointerMoved;
        }

        if (_titleBar is not null)
        {
            _titleBar.PointerMoved += OnPointerMoved;
        }

        ResetPosition();
    }

    /// <summary>
    /// Setzt den Service zurück und entfernt alle Fake-Buttons.
    /// </summary>
    public void Detach()
    {
        _overlay.SizeChanged -= OnOverlaySizeChanged;

        if (_window.Content is UIElement root)
        {
            root.PointerMoved -= OnPointerMoved;
        }

        if (_titleBar is not null)
        {
            _titleBar.PointerMoved -= OnPointerMoved;
        }

        _closeButton.Click -= OnCloseButtonClick;

        foreach (var fake in _fakeButtons.ToList())
        {
            _overlay.Children.Remove(fake);
        }

        _fakeButtons.Clear();
    }

    /// <summary>
    /// Positioniert den echten Schließen-Button initial oben rechts in der Titlebar.
    /// </summary>
    public void ResetPosition()
    {
        _evadeCount = 0;
        _stage3Active = false;
        _closeButton.Content = "X";
        _closeButton.Width = ButtonWidth;
        _closeButton.Height = ButtonHeight;
        _closeButton.FontSize = 16;
        _closeButton.FontWeight = Microsoft.UI.Text.FontWeights.SemiBold;
        _closeButton.Background = new SolidColorBrush(Microsoft.UI.Colors.Red);
        _closeButton.Foreground = new SolidColorBrush(Microsoft.UI.Colors.White);
        _closeButton.BorderThickness = new Thickness(0);
        _closeButton.IsHitTestVisible = true;

        RemoveFakes();
        PositionTopRight(_closeButton);
    }

    private void OnOverlaySizeChanged(object sender, SizeChangedEventArgs e)
    {
        KeepInside(_closeButton);
        foreach (var fake in _fakeButtons)
        {
            KeepInside(fake);
        }
    }

    private void OnPointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (_overlay.Visibility != Visibility.Visible)
        {
            return;
        }

        var point = e.GetCurrentPoint(_overlay);
        var position = point.Position;

        var buttonCenter = GetButtonCenter(_closeButton);
        double distance = Math.Sqrt(
            Math.Pow(position.X - buttonCenter.X, 2) +
            Math.Pow(position.Y - buttonCenter.Y, 2));

        if (distance < _config.StageThresholds.Stage1ProximityDip)
        {
            Evade();
        }
    }

    private void Evade()
    {
        if ((DateTime.Now - _lastEvade).TotalMilliseconds < 120)
        {
            return;
        }

        _lastEvade = DateTime.Now;
        _evadeCount++;

        if (_evadeCount >= _config.StageThresholds.Stage3AfterEvades)
        {
            EnterStage3();
        }
        else if (_evadeCount >= _config.StageThresholds.Stage2AfterEvades)
        {
            EnterStage2();
        }
        else
        {
            EnterStage1();
        }
    }

    private void EnterStage1()
    {
        ToolTipService.SetToolTip(_closeButton, _locale.CloseButton.Stage1Tooltip);
        AprilFoolsAudioService.Play(_locale.CloseButton.Stage1Audio);

        double currentLeft = Canvas.GetLeft(_closeButton);
        double half = _overlay.ActualWidth / 2;

        if (double.IsNaN(currentLeft) || currentLeft < half)
        {
            PositionTopRight(_closeButton);
        }
        else
        {
            PositionTopLeft(_closeButton);
        }
    }

    private void EnterStage2()
    {
        ToolTipService.SetToolTip(_closeButton, _locale.CloseButton.Stage2Tooltip);
        AprilFoolsAudioService.Play(_locale.CloseButton.Stage2Audio);

        double x = _random.NextDouble() * Math.Max(20, _overlay.ActualWidth - ButtonWidth - 40) + 20;
        double y = _random.NextDouble() * Math.Max(TitlebarHeight + 20, _overlay.ActualHeight - ButtonHeight - TitlebarHeight - 20) + TitlebarHeight + 20;

        Canvas.SetLeft(_closeButton, x);
        Canvas.SetTop(_closeButton, y);
        KeepInside(_closeButton);
    }

    private void EnterStage3()
    {
        ToolTipService.SetToolTip(_closeButton, _locale.CloseButton.Stage3Tooltip);
        AprilFoolsAudioService.Play(_locale.CloseButton.Stage3Audio);

        if (!_stage3Active)
        {
            _stage3Active = true;
            SpawnFakes();
        }

        // Echten Button ebenfalls wegspringen lassen.
        double x = _random.NextDouble() * Math.Max(20, _overlay.ActualWidth - ButtonWidth - 40) + 20;
        double y = _random.NextDouble() * Math.Max(20, _overlay.ActualHeight - ButtonHeight - 40) + 20;
        Canvas.SetLeft(_closeButton, x);
        Canvas.SetTop(_closeButton, y);
        KeepInside(_closeButton);
    }

    private void SpawnFakes()
    {
        RemoveFakes();

        for (int i = 0; i < _config.StageThresholds.FakeIconCount; i++)
        {
            var fake = new Button
            {
                Content = "X",
                Width = ButtonWidth,
                Height = ButtonHeight,
                FontSize = 16,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                Background = new SolidColorBrush(Microsoft.UI.Colors.DarkRed),
                Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
                BorderThickness = new Thickness(0),
                IsHitTestVisible = true,
            };

            fake.Click += OnFakeButtonClick;
            PlaceRandomly(fake);
            _overlay.Children.Add(fake);
            _fakeButtons.Add(fake);
        }
    }

    private void OnFakeButtonClick(object sender, RoutedEventArgs e)
    {
        AprilFoolsAudioService.Play(_locale.CloseButton.FakeClickAudio);

        if (sender is Button fake)
        {
            PlaceRandomly(fake);
        }
    }

    private void OnCloseButtonClick(object sender, RoutedEventArgs e)
    {
        AprilFoolsOrchestrator.RequestCustomClose();
    }

    private void RemoveFakes()
    {
        foreach (var fake in _fakeButtons)
        {
            fake.Click -= OnFakeButtonClick;
            _overlay.Children.Remove(fake);
        }

        _fakeButtons.Clear();
    }

    private void PlaceRandomly(Button button)
    {
        double x = _random.NextDouble() * Math.Max(10, _overlay.ActualWidth - ButtonWidth - 20) + 10;
        double y = _random.NextDouble() * Math.Max(10, _overlay.ActualHeight - ButtonHeight - 20) + 10;
        Canvas.SetLeft(button, x);
        Canvas.SetTop(button, y);
        KeepInside(button);
    }

    private void PositionTopRight(Button button)
    {
        Canvas.SetLeft(button, Math.Max(10, _overlay.ActualWidth - ButtonWidth - 20));
        Canvas.SetTop(button, 10);
    }

    private void PositionTopLeft(Button button)
    {
        Canvas.SetLeft(button, 20);
        Canvas.SetTop(button, 10);
    }

    private void KeepInside(Button button)
    {
        double x = Canvas.GetLeft(button);
        double y = Canvas.GetTop(button);

        if (double.IsNaN(x))
        {
            x = 0;
        }

        if (double.IsNaN(y))
        {
            y = 0;
        }

        double maxX = Math.Max(0, _overlay.ActualWidth - ButtonWidth);
        double maxY = Math.Max(0, _overlay.ActualHeight - ButtonHeight);

        x = Math.Clamp(x, 0, maxX);
        y = Math.Clamp(y, 0, maxY);

        Canvas.SetLeft(button, x);
        Canvas.SetTop(button, y);
    }

    private Windows.Foundation.Point GetButtonCenter(Button button)
    {
        double x = Canvas.GetLeft(button);
        double y = Canvas.GetTop(button);

        if (double.IsNaN(x))
        {
            x = 0;
        }

        if (double.IsNaN(y))
        {
            y = 0;
        }

        return new Windows.Foundation.Point(x + ButtonWidth / 2, y + ButtonHeight / 2);
    }
}
