using Microsoft.UI.Xaml;

namespace TARNO.UI.Services;

/// <summary>
/// Zusätzliche attached Properties, die an beliebige FrameworkElemente
/// gehängt werden können, um sie als verschiebbare Sektionen zu markieren.
/// </summary>
public static class DraggableInfo
{
    public static readonly DependencyProperty IsDraggableProperty =
        DependencyProperty.RegisterAttached(
            "IsDraggable",
            typeof(bool),
            typeof(DraggableInfo),
            new PropertyMetadata(false));

    public static bool GetIsDraggable(DependencyObject element)
        => (bool)element.GetValue(IsDraggableProperty);

    public static void SetIsDraggable(DependencyObject element, bool value)
        => element.SetValue(IsDraggableProperty, value);

    public static readonly DependencyProperty PanelIdProperty =
        DependencyProperty.RegisterAttached(
            "PanelId",
            typeof(string),
            typeof(DraggableInfo),
            new PropertyMetadata(string.Empty));

    public static string GetPanelId(DependencyObject element)
        => (string)element.GetValue(PanelIdProperty);

    public static void SetPanelId(DependencyObject element, string value)
        => element.SetValue(PanelIdProperty, value);

    public static readonly DependencyProperty TitleProperty =
        DependencyProperty.RegisterAttached(
            "Title",
            typeof(string),
            typeof(DraggableInfo),
            new PropertyMetadata("Panel"));

    public static string GetTitle(DependencyObject element)
        => (string)element.GetValue(TitleProperty);

    public static void SetTitle(DependencyObject element, string value)
        => element.SetValue(TitleProperty, value);

    public static readonly DependencyProperty PlaceholderProperty =
        DependencyProperty.RegisterAttached(
            "Placeholder",
            typeof(FrameworkElement),
            typeof(DraggableInfo),
            new PropertyMetadata(null));

    public static FrameworkElement? GetPlaceholder(DependencyObject element)
        => (FrameworkElement?)element.GetValue(PlaceholderProperty);

    public static void SetPlaceholder(DependencyObject element, FrameworkElement? value)
        => element.SetValue(PlaceholderProperty, value);

    public static readonly DependencyProperty OriginalParentProperty =
        DependencyProperty.RegisterAttached(
            "OriginalParent",
            typeof(DependencyObject),
            typeof(DraggableInfo),
            new PropertyMetadata(null));

    public static DependencyObject? GetOriginalParent(DependencyObject element)
        => (DependencyObject?)element.GetValue(OriginalParentProperty);

    public static void SetOriginalParent(DependencyObject element, DependencyObject? value)
        => element.SetValue(OriginalParentProperty, value);

    public static readonly DependencyProperty OriginalRowProperty =
        DependencyProperty.RegisterAttached(
            "OriginalRow",
            typeof(int),
            typeof(DraggableInfo),
            new PropertyMetadata(0));

    public static int GetOriginalRow(DependencyObject element)
        => (int)element.GetValue(OriginalRowProperty);

    public static void SetOriginalRow(DependencyObject element, int value)
        => element.SetValue(OriginalRowProperty, value);

    public static readonly DependencyProperty OriginalColumnProperty =
        DependencyProperty.RegisterAttached(
            "OriginalColumn",
            typeof(int),
            typeof(DraggableInfo),
            new PropertyMetadata(0));

    public static int GetOriginalColumn(DependencyObject element)
        => (int)element.GetValue(OriginalColumnProperty);

    public static void SetOriginalColumn(DependencyObject element, int value)
        => element.SetValue(OriginalColumnProperty, value);

    public static readonly DependencyProperty OriginalIndexProperty =
        DependencyProperty.RegisterAttached(
            "OriginalIndex",
            typeof(int),
            typeof(DraggableInfo),
            new PropertyMetadata(-1));

    public static int GetOriginalIndex(DependencyObject element)
        => (int)element.GetValue(OriginalIndexProperty);

    public static void SetOriginalIndex(DependencyObject element, int value)
        => element.SetValue(OriginalIndexProperty, value);
}
