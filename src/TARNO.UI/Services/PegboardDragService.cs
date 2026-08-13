using System;
using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;
using TARNO.UI.Controls;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Pointer-basiertes Drag-Handling für Elemente innerhalb eines SnapCanvas.
/// Bewegt das Element in Snap-to-Grid-Schritten, ohne das OS-Drag-Drop
/// auszulösen. Cross-Window-Drag wird absichtlich NICHT hier behandelt.
/// </summary>
public static class PegboardDragService
{
    private static SnapCanvas? _canvas;
    private static FrameworkElement? _element;
    private static Window? _window;
    private static int _startGridX;
    private static int _startGridY;
    private static double _startX;
    private static double _startY;
    private static double _startOpacity;
    private static bool _tearingOff;
    private static Border? _dragGhost;
    private static Grid? _dockHint;
    private static Border[] _dockZoneBorders = Array.Empty<Border>();
    private static UIElement? _dockTarget;
    private static DockZone _dockZone;
    private static Windows.Foundation.Rect _dockRect;
    private static Windows.Foundation.Rect _dockTargetOriginalRect;

    private enum DockZone
    {
        None,
        Left,
        Top,
        Right,
        Bottom,
        Center,
    }

    // Muss sicher ueber dem BringToFront-Panel-Bereich (max 1000) liegen, darf
    // aber nicht int.MaxValue sein: Canvas.SetZIndex() wirft in WinUI 3 nativ
    // ArgumentException ("Value does not fall within the expected range") fuer
    // Werte nahe Int32.MaxValue - stuerzte bisher bei jedem Klick auf einen
    // Panel-Header sofort in AttachDragGhost ab, noch bevor tatsaechlich
    // gezogen wurde.
    private const int AdornerZIndex = 100_000;

    public static bool IsDragging => _element is not null;

    public static void StartDrag(SnapCanvas canvas, FrameworkElement element, PointerPoint point)
        => StartDrag(canvas, element, point.Position);

    /// <summary>
    /// Nimmt bewusst einen reinen <see cref="Windows.Foundation.Point"/> statt
    /// eines <see cref="PointerPoint"/> - PointerPoint hat keinen oeffentlichen
    /// Konstruktor und laesst sich nicht synthetisch erzeugen, was einen
    /// automatisierten Selbsttest (ohne echte Maus-/Touch-Eingabe) unmoeglich
    /// gemacht haette. Diese Uebertaggung erlaubt <see cref="PegboardSelfTestService"/>,
    /// exakt dieselbe Drag-Logik wie ein echter Pointer-Press zu durchlaufen.
    /// </summary>
    public static void StartDrag(SnapCanvas canvas, FrameworkElement element, Windows.Foundation.Point point)
    {
        if (canvas is null || element is null || canvas.GridSize <= 0)
        {
            return;
        }

        _canvas = canvas;
        _element = element;
        _window = WindowStateCoordinator.GetWindowByXamlRoot(canvas.XamlRoot);
        _tearingOff = false;
        _startX = point.X;
        _startY = point.Y;
        _startGridX = SnapCanvas.GetGridX(element);
        _startGridY = SnapCanvas.GetGridY(element);
        _startOpacity = element.Opacity;

        // Dim the source panel so the drag ghost becomes the primary visual.
        element.Opacity = 0.5;

        BringToFront(canvas, element);
        AttachDragGhost(canvas, element);
        AttachDockHint(canvas);
        _ = element.Focus(FocusState.Pointer);
    }

    private static void AttachDockHint(SnapCanvas canvas)
    {
        if (_dockHint is not null)
        {
            return;
        }

        _dockHint = new Grid
        {
            IsHitTestVisible = false,
            Visibility = Visibility.Collapsed,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
        };

        _dockHint.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.5, GridUnitType.Star) });
        _dockHint.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        _dockHint.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.5, GridUnitType.Star) });

        _dockHint.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0.5, GridUnitType.Star) });
        _dockHint.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        _dockHint.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0.5, GridUnitType.Star) });

        _dockZoneBorders = new Border[6];
        var brush = new SolidColorBrush(Microsoft.UI.Colors.Cyan);

        AddZoneBorder(DockZone.Left, brush, 1, 0);
        AddZoneBorder(DockZone.Top, brush, 0, 1);
        AddZoneBorder(DockZone.Right, brush, 1, 2);
        AddZoneBorder(DockZone.Bottom, brush, 2, 1);
        AddZoneBorder(DockZone.Center, brush, 1, 1);

        SnapCanvas.SetIsAdorner(_dockHint, true);
        Canvas.SetZIndex(_dockHint, AdornerZIndex);
        canvas.Children.Add(_dockHint);
    }

    private static void AddZoneBorder(DockZone zone, SolidColorBrush brush, int row, int column)
    {
        if (_dockHint is null)
        {
            return;
        }

        var border = new Border
        {
            Background = brush,
            Opacity = 0.1,
            IsHitTestVisible = false,
        };

        Grid.SetRow(border, row);
        Grid.SetColumn(border, column);
        _dockZoneBorders[(int)zone] = border;
        _dockHint.Children.Add(border);
    }

    private static void AttachDragGhost(SnapCanvas canvas, FrameworkElement element)
    {
        if (_dragGhost is not null)
        {
            return;
        }

        int columns = SnapCanvas.GetGridColumns(element);
        int rows = SnapCanvas.GetGridRows(element);
        double scale = SnapCanvas.GetScale(element);

        _dragGhost = new Border
        {
            Background = new SolidColorBrush(Microsoft.UI.Colors.Cyan) { Opacity = 0.15 },
            BorderBrush = new SolidColorBrush(Microsoft.UI.Colors.Cyan) { Opacity = 0.5 },
            BorderThickness = new Thickness(1),
            IsHitTestVisible = false,
            Width = columns * canvas.GridSize * scale,
            Height = rows * canvas.GridSize * scale,
        };

        SnapCanvas.SetIsAdorner(_dragGhost, true);
        Canvas.SetZIndex(_dragGhost, AdornerZIndex - 1);
        Canvas.SetLeft(_dragGhost, _startGridX * canvas.GridSize);
        Canvas.SetTop(_dragGhost, _startGridY * canvas.GridSize);

        canvas.Children.Add(_dragGhost);
    }

    private static void BringToFront(Canvas canvas, FrameworkElement element)
    {
        // Previously capped at a hard maxPanelZ=1000 via Math.Min(maxZ + 1, 1000) -
        // after ~1000 drags in one session every subsequent bring-to-front computed
        // the same maxZ (999) and assigned the same capped value (1000) to whichever
        // panel was raised next, so multiple panels converged on one z-index and
        // "bring to front" silently stopped working. Fix: once the cap would be hit,
        // renumber all non-adorner panels contiguously from 1 first, so there's
        // always room above the current max instead of saturating.
        const int maxPanelZ = 1000;
        var others = new System.Collections.Generic.List<UIElement>();
        int maxZ = 0;
        foreach (var child in canvas.Children)
        {
            if (child is UIElement ui && ui != element && !SnapCanvas.GetIsAdorner(ui))
            {
                others.Add(ui);
                maxZ = Math.Max(maxZ, Canvas.GetZIndex(ui));
            }
        }

        if (maxZ + 1 >= maxPanelZ)
        {
            others.Sort((a, b) => Canvas.GetZIndex(a).CompareTo(Canvas.GetZIndex(b)));
            for (int i = 0; i < others.Count; i++)
            {
                Canvas.SetZIndex(others[i], i + 1);
            }
            maxZ = others.Count;
        }

        Canvas.SetZIndex(element, maxZ + 1);
    }

    public static void Move(PointerPoint point) => Move(point.Position);

    public static void Move(Windows.Foundation.Point point)
    {
        if (_canvas is null || _element is null || _tearingOff)
        {
            return;
        }

        if (_window is not null && IsPointerOutsideWindow(point))
        {
            _tearingOff = true;
            TearOff(point);
            return;
        }

        double deltaX = point.X - _startX;
        double deltaY = point.Y - _startY;

        var elementRect = _canvas.GetChildRect(_element);
        double rawX = _startGridX * _canvas.GridSize + deltaX;
        double rawY = _startGridY * _canvas.GridSize + deltaY;

        double canvasW = _canvas.ActualWidth > 0 ? _canvas.ActualWidth : _canvas.DesiredSize.Width;
        double canvasH = _canvas.ActualHeight > 0 ? _canvas.ActualHeight : _canvas.DesiredSize.Height;

        // Clamp the ghost to the visible canvas so the panel cannot be dragged out of bounds.
        rawX = Math.Max(0, Math.Min(rawX, canvasW - elementRect.Width));
        rawY = Math.Max(0, Math.Min(rawY, canvasH - elementRect.Height));

        if (_dragGhost is not null)
        {
            Canvas.SetLeft(_dragGhost, rawX);
            Canvas.SetTop(_dragGhost, rawY);
        }

        _canvas.InvalidateMeasure();
        UpdateDockHint(point);
    }

    private static void UpdateDockHint(Windows.Foundation.Point point)
    {
        if (_canvas is null || _element is null || _dockHint is null)
        {
            return;
        }

        UIElement? target = null;
        int maxZ = int.MinValue;

        foreach (UIElement child in _canvas.Children)
        {
            if (child is null || child == _element || child == _dragGhost || child == _dockHint || SnapCanvas.GetIsAdorner(child))
            {
                continue;
            }

            var rect = _canvas.GetChildRect(child);
            if (rect.Contains(point))
            {
                int z = Canvas.GetZIndex(child);
                if (z >= maxZ)
                {
                    maxZ = z;
                    target = child;
                }
            }
        }

        double canvasW = _canvas.ActualWidth > 0 ? _canvas.ActualWidth : _canvas.DesiredSize.Width;
        double canvasH = _canvas.ActualHeight > 0 ? _canvas.ActualHeight : _canvas.DesiredSize.Height;

        if (target is null)
        {
            if (TryUpdateContainerDockHint(point, canvasW, canvasH))
            {
                _canvas.InvalidateMeasure();
            }
            else
            {
                _dockHint.Visibility = Visibility.Collapsed;
                _dockTarget = null;
                _dockZone = DockZone.None;
            }

            return;
        }

        var targetRect = _canvas.GetChildRect(target);
        double relX = (point.X - targetRect.X) / targetRect.Width;
        double relY = (point.Y - targetRect.Y) / targetRect.Height;

        double x = targetRect.X;
        double y = targetRect.Y;
        double w = targetRect.Width;
        double h = targetRect.Height;
        DockZone zone;

        // Frueher deckte der "sonst"-Fall (Center) die gesamte Mitte ab
        // (alles ausserhalb der 25%-Randbaender) und zwang JEDEN Drop dort auf
        // ein Viertel der Zielgroesse, zentriert - unabhaengig von der
        // tatsaechlichen Mausposition. Da die Standard-Panels den Canvas fast
        // vollstaendig ausfuellen, landete man beim Ziehen praktisch immer
        // ueber einem anderen Panel, sodass freies Platzieren
        // (DropAtGhostPosition) nie zum Zug kam. Jetzt: nur noch ein schmales
        // Randband (15%) je Seite loest ueberhaupt ein Andocken aus; alles
        // dazwischen faellt durch und wird als "kein Ziel" behandelt, also
        // frei an der gezogenen Position abgelegt.
        const double edgeBand = 0.15;

        if (relX < edgeBand)
        {
            zone = DockZone.Left;
            w = targetRect.Width / 2;
        }
        else if (relX > 1 - edgeBand)
        {
            zone = DockZone.Right;
            x = targetRect.X + targetRect.Width / 2;
            w = targetRect.Width / 2;
        }
        else if (relY < edgeBand)
        {
            zone = DockZone.Top;
            h = targetRect.Height / 2;
        }
        else if (relY > 1 - edgeBand)
        {
            zone = DockZone.Bottom;
            y = targetRect.Y + targetRect.Height / 2;
            h = targetRect.Height / 2;
        }
        else
        {
            // Kein Rand getroffen: kein Andock-Ziel, sonst gilt fuer den Rest
            // von UpdateDockHint dasselbe wie fuer target is null oben -
            // Container-Andocken pruefen, sonst als freier Drop behandeln.
            if (TryUpdateContainerDockHint(point, canvasW, canvasH))
            {
                _canvas.InvalidateMeasure();
            }
            else
            {
                _dockHint.Visibility = Visibility.Collapsed;
                _dockTarget = null;
                _dockZone = DockZone.None;
            }

            return;
        }

        _dockHint.Visibility = Visibility.Visible;
        _dockHint.Width = targetRect.Width;
        _dockHint.Height = targetRect.Height;
        Canvas.SetLeft(_dockHint, targetRect.X);
        Canvas.SetTop(_dockHint, targetRect.Y);

        for (int i = 1; i < _dockZoneBorders.Length; i++)
        {
            if (_dockZoneBorders[i] is not null)
            {
                _dockZoneBorders[i].Opacity = 0.1;
            }
        }

        var active = _dockZoneBorders[(int)zone];
        if (active is not null)
        {
            active.Opacity = 0.4;
        }

        _dockTarget = target;
        _dockZone = zone;
        _dockRect = new Windows.Foundation.Rect(x, y, w, h);
        _dockTargetOriginalRect = targetRect;

        _canvas.InvalidateMeasure();
    }

    public static void End()
    {
        if (_canvas is not null && !_tearingOff && _element is not null && _dockTarget is not null)
        {
            ApplyDockRect();
        }
        else if (_canvas is not null && !_tearingOff && _element is not null && _dragGhost is not null)
        {
            DropAtGhostPosition();
        }

        if (_canvas is not null && !_tearingOff)
        {
            var validation = _canvas.ValidateLayout();
            if (!validation.IsValid)
            {
                InteractionLogger.Warn("PEGBOARD", validation.ToString());
            }
        }

        if (_element is IPegboardPanel panel && !_tearingOff)
        {
            PegboardService.SavePanelLayout(panel);
        }

        RemoveAdorners();

        _canvas = null;
        _element = null;
        _window = null;
        _tearingOff = false;
        _dockTarget = null;
        _dockZone = DockZone.None;
    }

    private static void DropAtGhostPosition()
    {
        if (_canvas is null || _element is null || _dragGhost is null)
        {
            return;
        }

        double left = Canvas.GetLeft(_dragGhost);
        double top = Canvas.GetTop(_dragGhost);

        var elementRect = _canvas.GetChildRect(_element);
        double canvasW = _canvas.ActualWidth > 0 ? _canvas.ActualWidth : _canvas.DesiredSize.Width;
        double canvasH = _canvas.ActualHeight > 0 ? _canvas.ActualHeight : _canvas.DesiredSize.Height;

        int maxGridX = (int)Math.Max(0, Math.Floor((canvasW - elementRect.Width) / _canvas.GridSize));
        int maxGridY = (int)Math.Max(0, Math.Floor((canvasH - elementRect.Height) / _canvas.GridSize));

        int gridX = Math.Max(0, Math.Min((int)Math.Round(left / _canvas.GridSize), maxGridX));
        int gridY = Math.Max(0, Math.Min((int)Math.Round(top / _canvas.GridSize), maxGridY));

        SnapCanvas.SetGridX(_element, gridX);
        SnapCanvas.SetGridY(_element, gridY);
        _canvas.InvalidateMeasure();
    }

    private static void ApplyDockRect()
    {
        if (_canvas is null || _element is null)
        {
            return;
        }

        ApplyGridRect(_element, _dockRect);

        // Tiling-Reflow: beim Andocken AUF einem anderen Panel (nicht beim
        // Andocken an den Canvas-Rand) bekommt das gezogene Panel per
        // ApplyGridRect() oben die halbe Zielflaeche - ohne diesen Block wuerde
        // das Ziel-Panel unveraendert an seiner alten vollen Groesse bleiben
        // und beide wuerden sich dauerhaft ueberlappen. Stattdessen weicht das
        // Ziel-Panel auf die komplementaere Haelfte seines urspruenglichen
        // Rechtecks aus (Left <-> Right, Top <-> Bottom), analog zu VS Code /
        // Windows Snap Assist.
        if (_dockTarget is IPegboardPanel targetPanel && !ReferenceEquals(_dockTarget, _canvas))
        {
            var remainder = ComputeRemainderRect(_dockTargetOriginalRect, _dockZone);
            if (remainder.Width > 0 && remainder.Height > 0)
            {
                ApplyGridRect(targetPanel.DragRoot, remainder);
            }
        }

        _canvas.InvalidateMeasure();
    }

    private static Windows.Foundation.Rect ComputeRemainderRect(Windows.Foundation.Rect original, DockZone zone)
    {
        double halfW = original.Width / 2;
        double halfH = original.Height / 2;

        return zone switch
        {
            DockZone.Left => new Windows.Foundation.Rect(original.X + halfW, original.Y, halfW, original.Height),
            DockZone.Right => new Windows.Foundation.Rect(original.X, original.Y, halfW, original.Height),
            DockZone.Top => new Windows.Foundation.Rect(original.X, original.Y + halfH, original.Width, halfH),
            DockZone.Bottom => new Windows.Foundation.Rect(original.X, original.Y, original.Width, halfH),
            _ => original,
        };
    }

    private static void ApplyGridRect(FrameworkElement element, Windows.Foundation.Rect pixelRect)
    {
        if (_canvas is null)
        {
            return;
        }

        double scale = SnapCanvas.GetScale(element);
        double canvasW = _canvas.ActualWidth > 0 ? _canvas.ActualWidth : _canvas.DesiredSize.Width;
        double canvasH = _canvas.ActualHeight > 0 ? _canvas.ActualHeight : _canvas.DesiredSize.Height;

        int maxGridX = (int)Math.Max(0, Math.Floor((canvasW - pixelRect.Width) / _canvas.GridSize));
        int maxGridY = (int)Math.Max(0, Math.Floor((canvasH - pixelRect.Height) / _canvas.GridSize));

        int gridX = Math.Max(0, Math.Min((int)Math.Round(pixelRect.X / _canvas.GridSize), maxGridX));
        int gridY = Math.Max(0, Math.Min((int)Math.Round(pixelRect.Y / _canvas.GridSize), maxGridY));
        int columns = Math.Max(1, (int)Math.Round(pixelRect.Width / (_canvas.GridSize * scale)));
        int rows = Math.Max(1, (int)Math.Round(pixelRect.Height / (_canvas.GridSize * scale)));

        // Clamp the docked size so it does not exceed the remaining canvas.
        int maxColumns = (int)Math.Max(1, Math.Floor((canvasW - gridX * _canvas.GridSize) / (_canvas.GridSize * scale)));
        int maxRows = (int)Math.Max(1, Math.Floor((canvasH - gridY * _canvas.GridSize) / (_canvas.GridSize * scale)));

        SnapCanvas.SetGridX(element, gridX);
        SnapCanvas.SetGridY(element, gridY);
        SnapCanvas.SetGridColumns(element, Math.Min(columns, maxColumns));
        SnapCanvas.SetGridRows(element, Math.Min(rows, maxRows));
    }

    private static void RemoveAdorners()
    {
        if (_dragGhost is not null)
        {
            if (_dragGhost.Parent is SnapCanvas canvas)
            {
                canvas.Children.Remove(_dragGhost);
            }
            _dragGhost = null;
        }

        if (_dockHint is not null)
        {
            if (_dockHint.Parent is SnapCanvas canvas)
            {
                canvas.Children.Remove(_dockHint);
            }
            _dockHint = null;
            _dockZoneBorders = Array.Empty<Border>();
        }

        if (_element is not null)
        {
            _element.Opacity = _startOpacity;
        }
    }

    private static bool TryUpdateContainerDockHint(Windows.Foundation.Point position, double canvasW, double canvasH)
    {
        if (_canvas is null || _dockHint is null)
        {
            return false;
        }

        // War 80px - bei einem 34px hohen Drag-Header reichte praktisch jede
        // gewoehnliche Ziehbewegung, um versehentlich diese Full-Width/Half-
        // Height-Andockzone bei (0,0) auszuloesen. Sobald ein Panel dadurch
        // einmal canvasgross wurde, kollabierte die Ziehbegrenzung in Move()
        // dauerhaft auf (0,0) (canvasW - elementRect.Width wurde <= 0) - das
        // Panel wirkte danach "festgeklebt" in der oberen linken Ecke.
        const double edgeThreshold = 24.0;
        DockZone zone = DockZone.None;
        double x = 0;
        double y = 0;
        double w = canvasW;
        double h = canvasH;

        bool nearLeft = position.X < edgeThreshold;
        bool nearRight = position.X > canvasW - edgeThreshold;
        bool nearTop = position.Y < edgeThreshold;
        bool nearBottom = position.Y > canvasH - edgeThreshold;

        if (nearLeft && position.X <= position.Y && position.X <= canvasH - position.Y)
        {
            zone = DockZone.Left;
            w = canvasW / 2;
        }
        else if (nearRight && canvasW - position.X <= position.Y && canvasW - position.X <= canvasH - position.Y)
        {
            zone = DockZone.Right;
            x = canvasW / 2;
            w = canvasW / 2;
        }
        else if (nearTop)
        {
            zone = DockZone.Top;
            h = canvasH / 2;
        }
        else if (nearBottom)
        {
            zone = DockZone.Bottom;
            y = canvasH / 2;
            h = canvasH / 2;
        }

        if (zone == DockZone.None)
        {
            return false;
        }

        _dockHint.Visibility = Visibility.Visible;
        _dockHint.Width = canvasW;
        _dockHint.Height = canvasH;
        Canvas.SetLeft(_dockHint, 0);
        Canvas.SetTop(_dockHint, 0);

        for (int i = 1; i < _dockZoneBorders.Length; i++)
        {
            if (_dockZoneBorders[i] is not null)
            {
                _dockZoneBorders[i].Opacity = 0.1;
            }
        }

        var active = _dockZoneBorders[(int)zone];
        if (active is not null)
        {
            active.Opacity = 0.4;
        }

        _dockTarget = _canvas;
        _dockZone = zone;
        _dockRect = new Windows.Foundation.Rect(x, y, w, h);
        return true;
    }

    private static bool IsPointerOutsideWindow(Windows.Foundation.Point point)
    {
        if (_canvas is null || _window is null)
        {
            return false;
        }

        var rootPoint = _canvas.TransformToVisual(null).TransformPoint(point);
        if (_window.Content is not FrameworkElement root)
        {
            return false;
        }

        const double tolerance = 4;
        return rootPoint.X < -tolerance
            || rootPoint.Y < -tolerance
            || rootPoint.X > root.ActualWidth + tolerance
            || rootPoint.Y > root.ActualHeight + tolerance;
    }

    private static void TearOff(Windows.Foundation.Point point)
    {
        if (_canvas is null || _element is null || _window is null || _element is not IPegboardPanel panel)
        {
            End();
            return;
        }

        var rootPoint = _canvas.TransformToVisual(null).TransformPoint(point);
        var scale = _canvas.XamlRoot?.RasterizationScale ?? 1.0;
        var appWindow = _window.AppWindow;
        if (appWindow is null)
        {
            End();
            return;
        }

        int screenX = (int)(appWindow.Position.X + rootPoint.X * scale);
        int screenY = (int)(appWindow.Position.Y + rootPoint.Y * scale);
        int width = (int)Math.Max(panel.DragRoot.ActualWidth * scale, 400);
        int height = (int)Math.Max(panel.DragRoot.ActualHeight * scale, 300);

        int displayIndex = MultiScreenLayoutService.FindDisplayForPoint(new PointInt32(screenX, screenY));
        var bounds = new RectModel
        {
            X = screenX,
            Y = screenY,
            Width = width,
            Height = height,
        };

        // Muss vor dem Reparenting passieren - sonst bleibt die Pointer-Capture
        // des Headers am alten Fenster haengen und das naechste Pointer-Ereignis
        // stuerzt beim Routing auf den fensterfremden Header ab.
        panel.ReleaseDragCapture();

        DockingService.UndockToNewWindow(panel, displayIndex, bounds, createPlaceholder: false);
        End();
    }
}
