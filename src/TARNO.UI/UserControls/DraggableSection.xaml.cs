using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Markup;
using Microsoft.UI.Xaml.Media;
using TARNO.UI.Controls;
using TARNO.UI.Models;
using TARNO.UI.Services;

namespace TARNO.UI.UserControls;

[ContentProperty(Name = "SectionContent")]
public sealed partial class DraggableSection : UserControl, IPegboardPanel
{
    public static readonly DependencyProperty TitleProperty =
        DependencyProperty.Register(
            nameof(Title),
            typeof(string),
            typeof(DraggableSection),
            new PropertyMetadata("Section"));

    public static readonly DependencyProperty PanelIdProperty =
        DependencyProperty.Register(
            nameof(PanelId),
            typeof(string),
            typeof(DraggableSection),
            new PropertyMetadata(string.Empty));

    public static readonly DependencyProperty WindowIndexProperty =
        DependencyProperty.Register(
            nameof(WindowIndex),
            typeof(int),
            typeof(DraggableSection),
            new PropertyMetadata(0));

    public static readonly DependencyProperty PlaceholderProperty =
        DependencyProperty.Register(
            nameof(Placeholder),
            typeof(FrameworkElement),
            typeof(DraggableSection),
            new PropertyMetadata(null));

    public static readonly DependencyProperty SectionContentProperty =
        DependencyProperty.Register(
            nameof(SectionContent),
            typeof(object),
            typeof(DraggableSection),
            new PropertyMetadata(null, OnSectionContentChanged));

    public DraggableSection()
    {
        this.InitializeComponent();
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        var pegged = IsInsideSnapCanvas();
        if (ResizeGrip is not null)
        {
            ResizeGrip.Visibility = pegged ? Visibility.Visible : Visibility.Collapsed;
        }

        if (RightResizeHandle is not null)
        {
            RightResizeHandle.Visibility = pegged ? Visibility.Visible : Visibility.Collapsed;
        }

        if (BottomResizeHandle is not null)
        {
            BottomResizeHandle.Visibility = pegged ? Visibility.Visible : Visibility.Collapsed;
        }

        if (PopOutButton is not null)
        {
            PopOutButton.Visibility = pegged ? Visibility.Visible : Visibility.Collapsed;
        }
    }

    private SnapCanvas? FindSnapCanvasParent()
    {
        DependencyObject? current = this;
        while (current is not null)
        {
            if (current is SnapCanvas canvas)
            {
                return canvas;
            }

            current = VisualTreeHelper.GetParent(current);
        }

        return null;
    }

    private bool IsInsideSnapCanvas() => FindSnapCanvasParent() is not null;

    public int GridX
    {
        get => SnapCanvas.GetGridX(this);
        set => SnapCanvas.SetGridX(this, value);
    }

    public int GridY
    {
        get => SnapCanvas.GetGridY(this);
        set => SnapCanvas.SetGridY(this, value);
    }

    public int GridColumns
    {
        get => SnapCanvas.GetGridColumns(this);
        set => SnapCanvas.SetGridColumns(this, value);
    }

    public int GridRows
    {
        get => SnapCanvas.GetGridRows(this);
        set => SnapCanvas.SetGridRows(this, value);
    }

    public new double Scale
    {
        get => SnapCanvas.GetScale(this);
        set => SnapCanvas.SetScale(this, value);
    }

    public bool IsPegged => IsInsideSnapCanvas();

    public string Title
    {
        get => (string)GetValue(TitleProperty);
        set => SetValue(TitleProperty, value);
    }

    public string PanelId
    {
        get => (string)GetValue(PanelIdProperty);
        set => SetValue(PanelIdProperty, value);
    }

    public int WindowIndex
    {
        get => (int)GetValue(WindowIndexProperty);
        set => SetValue(WindowIndexProperty, value);
    }

    public FrameworkElement? Placeholder
    {
        get => (FrameworkElement?)GetValue(PlaceholderProperty);
        set => SetValue(PlaceholderProperty, value);
    }

    public FrameworkElement DragRoot => this;

    public object? SectionContent
    {
        get => GetValue(SectionContentProperty);
        set => SetValue(SectionContentProperty, value);
    }

    private static void OnSectionContentChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is DraggableSection section && section.SectionContentPresenter is not null)
        {
            section.SectionContentPresenter.Content = e.NewValue;
        }
    }

    private void OnHeaderPointerPressed(object sender, PointerRoutedEventArgs e)
    {
        if (!IsInsideSnapCanvas())
        {
            return;
        }

        if (FindSnapCanvasParent() is not SnapCanvas canvas)
        {
            return;
        }

        var point = e.GetCurrentPoint(canvas);
        PegboardDragService.StartDrag(canvas, this, point);
        DragHeader?.CapturePointer(e.Pointer);
        e.Handled = true;
    }

    private void OnHeaderPointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!PegboardDragService.IsDragging)
        {
            return;
        }

        if (FindSnapCanvasParent() is not SnapCanvas canvas)
        {
            PegboardDragService.End();
            return;
        }

        var point = e.GetCurrentPoint(canvas);
        PegboardDragService.Move(point);
        e.Handled = true;
    }

    private void OnHeaderPointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (!PegboardDragService.IsDragging)
        {
            return;
        }

        PegboardDragService.End();
        DragHeader?.ReleasePointerCapture(e.Pointer);
        e.Handled = true;
    }

    private void OnResizePointerPressed(object sender, PointerRoutedEventArgs e)
    {
        if (FindSnapCanvasParent() is not SnapCanvas canvas)
        {
            return;
        }

        var mode = ResizeMode.Both;
        if (sender is FrameworkElement fe && fe.Tag is string tag)
        {
            _ = Enum.TryParse(tag, out mode);
        }

        var point = e.GetCurrentPoint(canvas);
        PegboardResizeService.StartResize(canvas, this, point, mode);
        if (sender is UIElement ui)
        {
            _ = ui.CapturePointer(e.Pointer);
        }
        e.Handled = true;
    }

    private void OnResizePointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!PegboardResizeService.IsResizing)
        {
            return;
        }

        if (FindSnapCanvasParent() is not SnapCanvas canvas)
        {
            PegboardResizeService.End();
            return;
        }

        var point = e.GetCurrentPoint(canvas);
        PegboardResizeService.Move(point);
        e.Handled = true;
    }

    private void OnResizePointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (!PegboardResizeService.IsResizing)
        {
            return;
        }

        PegboardResizeService.End();
        if (sender is UIElement ui)
        {
            ui.ReleasePointerCapture(e.Pointer);
        }
        e.Handled = true;
    }

    private void OnPopOutClick(object sender, RoutedEventArgs e)
    {
        PegboardService.PopOutToMonitor(this);
    }

    public void ReleaseDragCapture()
    {
        DragHeader?.ReleasePointerCaptures();
    }
}
