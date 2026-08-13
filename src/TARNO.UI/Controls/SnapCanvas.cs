using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Windows.Foundation;

namespace TARNO.UI.Controls;

/// <summary>
/// Ein Canvas-basiertes Layout-Panel, das seine Children an einem
/// unsichtbaren Raster ausrichtet (Snap-to-Grid). Jeder Child legt
/// Gitterposition und -spanne über Attached Properties fest; optional
/// kann ein Skalierungsfaktor angewendet werden.
/// </summary>
public class SnapCanvas : Canvas
{
    public static readonly DependencyProperty GridXProperty =
        DependencyProperty.RegisterAttached(
            "GridX",
            typeof(int),
            typeof(SnapCanvas),
            new PropertyMetadata(0, OnLayoutPropertyChanged));

    public static readonly DependencyProperty GridYProperty =
        DependencyProperty.RegisterAttached(
            "GridY",
            typeof(int),
            typeof(SnapCanvas),
            new PropertyMetadata(0, OnLayoutPropertyChanged));

    public static readonly DependencyProperty GridColumnsProperty =
        DependencyProperty.RegisterAttached(
            "GridColumns",
            typeof(int),
            typeof(SnapCanvas),
            new PropertyMetadata(1, OnLayoutPropertyChanged));

    public static readonly DependencyProperty GridRowsProperty =
        DependencyProperty.RegisterAttached(
            "GridRows",
            typeof(int),
            typeof(SnapCanvas),
            new PropertyMetadata(1, OnLayoutPropertyChanged));

    public static readonly DependencyProperty ScaleProperty =
        DependencyProperty.RegisterAttached(
            "Scale",
            typeof(double),
            typeof(SnapCanvas),
            new PropertyMetadata(1.0, OnLayoutPropertyChanged));

    public static readonly DependencyProperty IsAdornerProperty =
        DependencyProperty.RegisterAttached(
            "IsAdorner",
            typeof(bool),
            typeof(SnapCanvas),
            new PropertyMetadata(false));

    public static readonly DependencyProperty GridSizeProperty =
        DependencyProperty.Register(
            nameof(GridSize),
            typeof(int),
            typeof(SnapCanvas),
            new PropertyMetadata(24, OnGridSizeChanged));

    public int GridSize
    {
        get => (int)GetValue(GridSizeProperty);
        set => SetValue(GridSizeProperty, value);
    }

    public static int GetGridX(DependencyObject element)
    {
        return element is null ? 0 : (int)element.GetValue(GridXProperty);
    }

    public static void SetGridX(DependencyObject element, int value)
    {
        element?.SetValue(GridXProperty, value);
    }

    public static int GetGridY(DependencyObject element)
    {
        return element is null ? 0 : (int)element.GetValue(GridYProperty);
    }

    public static void SetGridY(DependencyObject element, int value)
    {
        element?.SetValue(GridYProperty, value);
    }

    public static int GetGridColumns(DependencyObject element)
    {
        return element is null ? 1 : (int)element.GetValue(GridColumnsProperty);
    }

    public static void SetGridColumns(DependencyObject element, int value)
    {
        element?.SetValue(GridColumnsProperty, Math.Max(1, value));
    }

    public static int GetGridRows(DependencyObject element)
    {
        return element is null ? 1 : (int)element.GetValue(GridRowsProperty);
    }

    public static void SetGridRows(DependencyObject element, int value)
    {
        element?.SetValue(GridRowsProperty, Math.Max(1, value));
    }

    public static double GetScale(DependencyObject element)
    {
        return element is null ? 1.0 : (double)element.GetValue(ScaleProperty);
    }

    public static void SetScale(DependencyObject element, double value)
    {
        element?.SetValue(ScaleProperty, Math.Max(0.25, value));
    }

    public static bool GetIsAdorner(DependencyObject element)
    {
        return element is not null && (bool)element.GetValue(IsAdornerProperty);
    }

    public static void SetIsAdorner(DependencyObject element, bool value)
    {
        element?.SetValue(IsAdornerProperty, value);
    }

    private static void OnLayoutPropertyChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is FrameworkElement element
            && element.Parent is SnapCanvas canvas)
        {
            canvas.InvalidateMeasure();
        }
    }

    private static void OnGridSizeChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is SnapCanvas canvas)
        {
            canvas.InvalidateMeasure();
        }
    }

    protected override Size MeasureOverride(Size availableSize)
    {
        double maxWidth = 0;
        double maxHeight = 0;

        foreach (UIElement child in Children)
        {
            if (child is null)
            {
                continue;
            }

            bool isAdorner = GetIsAdorner(child);
            var (cellX, cellY, cellColumns, cellRows, scale) = GetChildMetrics(child);
            double childWidth = cellColumns * GridSize * scale;
            double childHeight = cellRows * GridSize * scale;

            if (isAdorner)
            {
                child.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));
                continue;
            }

            child.Measure(new Size(childWidth, childHeight));

            double right = (cellX * GridSize) + child.DesiredSize.Width;
            double bottom = (cellY * GridSize) + child.DesiredSize.Height;

            if (right > maxWidth)
            {
                maxWidth = right;
            }

            if (bottom > maxHeight)
            {
                maxHeight = bottom;
            }
        }

        return new Size(Math.Max(0, maxWidth), Math.Max(0, maxHeight));
    }

    protected override Size ArrangeOverride(Size finalSize)
    {
        foreach (UIElement child in Children)
        {
            if (child is null)
            {
                continue;
            }

            Windows.Foundation.Rect rect;
            if (GetIsAdorner(child))
            {
                double x = Canvas.GetLeft(child);
                double y = Canvas.GetTop(child);
                if (double.IsNaN(x))
                {
                    x = 0;
                }

                if (double.IsNaN(y))
                {
                    y = 0;
                }

                rect = new Windows.Foundation.Rect(x, y, child.DesiredSize.Width, child.DesiredSize.Height);
            }
            else
            {
                var (cellX, cellY, cellColumns, cellRows, scale) = GetChildMetrics(child);
                double x = cellX * GridSize;
                double y = cellY * GridSize;
                double width = cellColumns * GridSize * scale;
                double height = cellRows * GridSize * scale;
                rect = new Windows.Foundation.Rect(x, y, width, height);
            }

            child.Arrange(rect);
        }

        return finalSize;
    }

    /// <summary>
    /// Berechnet das Pixel-Rechteck eines Kindes unter Berücksichtigung von
    /// GridSize und Scale. Bei Adornern wird Canvas.Left/Top verwendet.
    /// </summary>
    public Windows.Foundation.Rect GetChildRect(UIElement child)
    {
        if (GetIsAdorner(child))
        {
            double x = Canvas.GetLeft(child);
            double y = Canvas.GetTop(child);
            if (double.IsNaN(x))
            {
                x = 0;
            }

            if (double.IsNaN(y))
            {
                y = 0;
            }

            return new Windows.Foundation.Rect(x, y, child.DesiredSize.Width, child.DesiredSize.Height);
        }

        var (cellX, cellY, cellColumns, cellRows, scale) = GetChildMetrics(child);
        double x0 = cellX * GridSize;
        double y0 = cellY * GridSize;
        double width = cellColumns * GridSize * scale;
        double height = cellRows * GridSize * scale;
        return new Windows.Foundation.Rect(x0, y0, width, height);
    }

    /// <summary>
    /// Prüft das aktuelle Layout auf Überschneidungen und out-of-bounds.
    /// Kann ohne sichtbaren UI-Thread aufgerufen werden, solange Children
    /// vorhanden sind. Liefert detaillierte Warnmeldungen zurück.
    /// </summary>
    public SnapCanvasLayoutValidationResult ValidateLayout()
    {
        var result = new SnapCanvasLayoutValidationResult();
        var rects = new System.Collections.Generic.List<(UIElement child, Windows.Foundation.Rect rect)>();

        foreach (UIElement child in Children)
        {
            if (child is null || GetIsAdorner(child))
            {
                continue;
            }

            rects.Add((child, GetChildRect(child)));
        }

        for (int i = 0; i < rects.Count; i++)
        {
            var (childA, rectA) = rects[i];
            string nameA = childA is FrameworkElement feA && !string.IsNullOrEmpty(feA.Name) ? feA.Name : childA.GetType().Name;

            if (rectA.X < 0 || rectA.Y < 0)
            {
                result.Warnings.Add($"'{nameA}' liegt außerhalb des sichtbaren Bereichs (X={rectA.X}, Y={rectA.Y}).");
            }

            for (int j = i + 1; j < rects.Count; j++)
            {
                var (childB, rectB) = rects[j];
                if (RectsOverlap(rectA, rectB))
                {
                    string nameB = childB is FrameworkElement feB && !string.IsNullOrEmpty(feB.Name) ? feB.Name : childB.GetType().Name;
                    var overlap = rectA;
                    overlap.Intersect(rectB);
                    result.Warnings.Add($"Überschneidung zwischen '{nameA}' und '{nameB}' (Bereich: {overlap.Width}x{overlap.Height}).");
                }
            }
        }

        result.IsValid = result.Warnings.Count == 0;
        return result;
    }

    private static bool RectsOverlap(Windows.Foundation.Rect a, Windows.Foundation.Rect b)
    {
        return a.X < b.X + b.Width
            && a.X + a.Width > b.X
            && a.Y < b.Y + b.Height
            && a.Y + a.Height > b.Y;
    }

    private static (int x, int y, int columns, int rows, double scale) GetChildMetrics(UIElement child)
    {
        int x = GetGridX(child);
        int y = GetGridY(child);
        int columns = Math.Max(1, GetGridColumns(child));
        int rows = Math.Max(1, GetGridRows(child));
        double scale = Math.Max(0.25, GetScale(child));
        return (x, y, columns, rows, scale);
    }
}

/// <summary>
/// Ergebnis einer <see cref="SnapCanvas.ValidateLayout"/>-Prüfung.
/// </summary>
public class SnapCanvasLayoutValidationResult
{
    public bool IsValid { get; internal set; }

    public System.Collections.Generic.List<string> Warnings { get; } = new();

    public override string ToString()
    {
        if (Warnings.Count == 0)
        {
            return "Layout gültig.";
        }

        return string.Join("; ", Warnings);
    }
}
