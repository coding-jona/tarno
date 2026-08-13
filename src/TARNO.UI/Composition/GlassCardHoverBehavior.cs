using System.Numerics;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Hosting;
using Windows.UI.ViewManagement;

namespace TARNO.UI.Composition;

/// <summary>
/// Hover-Aufhellung für Glas-Karten (<see cref="GlassStyles"/> GlassCardStyle).
/// <see cref="Border"/> ist kein <see cref="Microsoft.UI.Xaml.Controls.Control"/>
/// und unterstützt daher keine VisualState-basierte Hover-Reaktion — dieses
/// Verhalten fügt stattdessen ein einmalig erzeugtes Composition-Overlay
/// (abgerundetes Rechteck, Füllung + Rand in Hover-Farben, Start-Opacity 0)
/// hinzu und animiert bei PointerEntered/PointerExited nur dessen Opacity.
/// Gleiches Attached-Property- und Animationsmuster wie
/// <see cref="SpecularHighlightBehavior"/> bzw. BlobBackground.AnimateDrift.
/// </summary>
public static class GlassCardHoverBehavior
{
    private const float HoverDurationMs = 200f;

    public static readonly DependencyProperty IsEnabledProperty = DependencyProperty.RegisterAttached(
        "IsEnabled",
        typeof(bool),
        typeof(GlassCardHoverBehavior),
        new PropertyMetadata(false, OnIsEnabledChanged));

    public static bool GetIsEnabled(Border element) => (bool)element.GetValue(IsEnabledProperty);

    public static void SetIsEnabled(Border element, bool value) => element.SetValue(IsEnabledProperty, value);

    private static void OnIsEnabledChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not Border border)
        {
            return;
        }

        if ((bool)e.NewValue)
        {
            Attach(border);
        }
    }

    private static void Attach(Border border)
    {
        var elementVisual = ElementCompositionPreview.GetElementVisual(border);
        var compositor = elementVisual.Compositor;

        var cornerRadius = (float)border.CornerRadius.TopLeft;

        var geometry = compositor.CreateRoundedRectangleGeometry();
        geometry.CornerRadius = new Vector2(cornerRadius, cornerRadius);
        geometry.Size = new Vector2((float)border.ActualWidth, (float)border.ActualHeight);

        var shape = compositor.CreateSpriteShape(geometry);
        shape.FillBrush = compositor.CreateColorBrush(Windows.UI.Color.FromArgb(15, 255, 255, 255)); // GlassCardBackgroundHoverBrush (~0.06)
        shape.StrokeBrush = compositor.CreateColorBrush(Windows.UI.Color.FromArgb(38, 255, 255, 255)); // GlassCardBorderHoverBrush (~0.15)
        shape.StrokeThickness = 1f;

        var overlay = compositor.CreateShapeVisual();
        overlay.Size = geometry.Size;
        overlay.Shapes.Add(shape);
        overlay.Opacity = 0f;

        ElementCompositionPreview.SetElementChildVisual(border, overlay);

        border.SizeChanged += (_, args) =>
        {
            var size = new Vector2((float)args.NewSize.Width, (float)args.NewSize.Height);
            geometry.Size = size;
            overlay.Size = size;
        };

        border.PointerEntered += (_, _) => AnimateOpacity(compositor, overlay, 1f);
        border.PointerExited += (_, _) => AnimateOpacity(compositor, overlay, 0f);
    }

    private static void AnimateOpacity(Compositor compositor, Visual visual, float target)
    {
        if (!new UISettings().AnimationsEnabled)
        {
            visual.Opacity = target;
            return;
        }

        var animation = compositor.CreateScalarKeyFrameAnimation();
        animation.InsertKeyFrame(1.0f, target);
        animation.Duration = System.TimeSpan.FromMilliseconds(HoverDurationMs);
        visual.StartAnimation("Opacity", animation);
    }
}
