using System;
using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using TARNO.UI.Controls;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

public enum ResizeMode
{
    Both,
    Horizontal,
    Vertical,
}

/// <summary>
/// Pointer-basiertes Resize für Elemente innerhalb eines SnapCanvas.
/// Verändert die GridColumns/GridRows in Snap-to-Grid-Schritten.
/// </summary>
public static class PegboardResizeService
{
    private static SnapCanvas? _canvas;
    private static FrameworkElement? _element;
    private static int _startColumns;
    private static int _startRows;
    private static double _startX;
    private static double _startY;
    private static ResizeMode _mode;

    public static bool IsResizing => _element is not null;

    public static void StartResize(SnapCanvas canvas, FrameworkElement element, PointerPoint point)
    {
        StartResize(canvas, element, point, ResizeMode.Both);
    }

    public static void StartResize(SnapCanvas canvas, FrameworkElement element, PointerPoint point, ResizeMode mode)
    {
        if (canvas is null || element is null || canvas.GridSize <= 0)
        {
            return;
        }

        _canvas = canvas;
        _element = element;
        _mode = mode;
        _startX = point.Position.X;
        _startY = point.Position.Y;
        _startColumns = SnapCanvas.GetGridColumns(element);
        _startRows = SnapCanvas.GetGridRows(element);
    }

    public static void Move(PointerPoint point)
    {
        if (_canvas is null || _element is null)
        {
            return;
        }

        double deltaX = point.Position.X - _startX;
        double deltaY = point.Position.Y - _startY;
        double scale = SnapCanvas.GetScale(_element);
        int colDelta = (int)Math.Round(deltaX / (_canvas.GridSize * scale));
        int rowDelta = (int)Math.Round(deltaY / (_canvas.GridSize * scale));

        const double minWidth = 120.0;
        const double minHeight = 96.0;
        int minColumns = Math.Max(1, (int)(minWidth / _canvas.GridSize));
        int minRows = Math.Max(1, (int)(minHeight / _canvas.GridSize));

        int newColumns = _mode != ResizeMode.Vertical
            ? Math.Max(minColumns, _startColumns + colDelta)
            : _startColumns;
        int newRows = _mode != ResizeMode.Horizontal
            ? Math.Max(minRows, _startRows + rowDelta)
            : _startRows;

        // Clamp to the remaining canvas so the panel cannot grow beyond the visible area.
        double canvasW = _canvas.ActualWidth > 0 ? _canvas.ActualWidth : _canvas.DesiredSize.Width;
        double canvasH = _canvas.ActualHeight > 0 ? _canvas.ActualHeight : _canvas.DesiredSize.Height;
        int gridX = SnapCanvas.GetGridX(_element);
        int gridY = SnapCanvas.GetGridY(_element);

        int maxColumns = (int)Math.Max(minColumns, Math.Floor((canvasW - gridX * _canvas.GridSize) / (_canvas.GridSize * scale)));
        int maxRows = (int)Math.Max(minRows, Math.Floor((canvasH - gridY * _canvas.GridSize) / (_canvas.GridSize * scale)));

        newColumns = Math.Min(newColumns, maxColumns);
        newRows = Math.Min(newRows, maxRows);

        if (newColumns != SnapCanvas.GetGridColumns(_element) || newRows != SnapCanvas.GetGridRows(_element))
        {
            SnapCanvas.SetGridColumns(_element, newColumns);
            SnapCanvas.SetGridRows(_element, newRows);
            _canvas.InvalidateMeasure();
        }
    }

    public static void End()
    {
        if (_canvas is not null)
        {
            var validation = _canvas.ValidateLayout();
            if (!validation.IsValid)
            {
                InteractionLogger.Warn("PEGBOARD", validation.ToString());
            }
        }

        if (_element is IPegboardPanel panel)
        {
            PegboardService.SavePanelLayout(panel);
        }

        _canvas = null;
        _element = null;
    }
}
