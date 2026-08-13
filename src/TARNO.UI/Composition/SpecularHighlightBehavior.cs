using System.Numerics;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;

namespace TARNO.UI.Composition;

/// <summary>
/// Fester, unbeweglicher Specular-Highlight für Glas-Flächen — kein Zeiger-
/// Tracking (der Nutzer will ein ruhiges, sitzendes Design, keine an die
/// Mausposition gekoppelte "Taschenlampe"). Entspricht dem finalen, festen
/// Glanzpunkt aus dem Orb-Referenz-Artefakt (".orb::before", das dort
/// bewusst von einem Cursor-Spotlight auf einen festen, sanften Schein
/// umgestellt wurde — siehe dessen CSS-Kommentar "fixed, gentle sheen —
/// replaces the old harsh cursor spotlight"). Kein Win2D/Pixel-Shader
/// nötig (siehe docs/liquid-glass-research.md, Abschnitt 4, Option A).
/// </summary>
public static class SpecularHighlightBehavior
{
    public static readonly DependencyProperty IsEnabledProperty = DependencyProperty.RegisterAttached(
        "IsEnabled",
        typeof(bool),
        typeof(SpecularHighlightBehavior),
        new PropertyMetadata(false, OnIsEnabledChanged));

    public static bool GetIsEnabled(FrameworkElement element) => (bool)element.GetValue(IsEnabledProperty);

    public static void SetIsEnabled(FrameworkElement element, bool value) => element.SetValue(IsEnabledProperty, value);

    private static void OnIsEnabledChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not FrameworkElement element)
        {
            return;
        }

        if ((bool)e.NewValue)
        {
            Attach(element);
        }
    }

    private static void Attach(FrameworkElement element)
    {
        var elementVisual = ElementCompositionPreview.GetElementVisual(element);
        var compositor = elementVisual.Compositor;

        var gradient = compositor.CreateRadialGradientBrush();
        gradient.EllipseRadius = new Vector2(220f, 180f);
        gradient.ColorStops.Insert(0, compositor.CreateColorGradientStop(0.0f, Windows.UI.Color.FromArgb(100, 255, 255, 255)));
        gradient.ColorStops.Insert(1, compositor.CreateColorGradientStop(1.0f, Windows.UI.Color.FromArgb(0, 255, 255, 255)));
        gradient.MappingMode = CompositionMappingMode.Absolute;

        var highlightVisual = compositor.CreateSpriteVisual();
        highlightVisual.Brush = gradient;
        highlightVisual.Opacity = 0.5f;
        highlightVisual.Size = new Vector2((float)element.ActualWidth, (float)element.ActualHeight);

        void PositionFixedSheen(float width, float height)
        {
            // Fest oben-links, nicht an den Zeiger gekoppelt.
            gradient.EllipseCenter = new Vector2(width * 0.28f, height * 0.08f);
        }

        PositionFixedSheen((float)element.ActualWidth, (float)element.ActualHeight);
        ElementCompositionPreview.SetElementChildVisual(element, highlightVisual);

        element.SizeChanged += (_, args) =>
        {
            highlightVisual.Size = new Vector2((float)args.NewSize.Width, (float)args.NewSize.Height);
            PositionFixedSheen((float)args.NewSize.Width, (float)args.NewSize.Height);
        };
    }
}
