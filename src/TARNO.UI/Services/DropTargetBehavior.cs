using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace TARNO.UI.Services;

/// <summary>
/// Attached Behavior, das jedem UIElement Drop-Unterstützung verleiht.
/// Standard-Fensterindex ist 0 (Hauptfenster); PanelWindow etc. setzen den
/// eigenen Index per AttachedProperty.
/// </summary>
public static class DropTargetBehavior
{
    public static readonly DependencyProperty IsDropTargetProperty =
        DependencyProperty.RegisterAttached(
            "IsDropTarget",
            typeof(bool),
            typeof(DropTargetBehavior),
            new PropertyMetadata(false, OnIsDropTargetChanged));

    public static readonly DependencyProperty TargetWindowIndexProperty =
        DependencyProperty.RegisterAttached(
            "TargetWindowIndex",
            typeof(int),
            typeof(DropTargetBehavior),
            new PropertyMetadata(0));

    public static bool GetIsDropTarget(DependencyObject element)
        => (bool)element.GetValue(IsDropTargetProperty);

    public static void SetIsDropTarget(DependencyObject element, bool value)
        => element.SetValue(IsDropTargetProperty, value);

    public static int GetTargetWindowIndex(DependencyObject element)
        => (int)element.GetValue(TargetWindowIndexProperty);

    public static void SetTargetWindowIndex(DependencyObject element, int value)
        => element.SetValue(TargetWindowIndexProperty, value);

    private static void OnIsDropTargetChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not UIElement element)
        {
            return;
        }

        if ((bool)e.NewValue)
        {
            element.AllowDrop = true;
            element.DragOver += OnDragOver;
            element.Drop += OnDrop;
        }
        else
        {
            element.DragOver -= OnDragOver;
            element.Drop -= OnDrop;
        }
    }

    private static void OnDragOver(object sender, DragEventArgs e)
    {
        PanelDragService.AcceptDrop(e);
    }

    private static void OnDrop(object sender, DragEventArgs e)
    {
        if (sender is not UIElement element)
        {
            return;
        }

        int index = GetTargetWindowIndex(element);
        PanelDragService.HandleDropAsync(index, e);
    }
}
