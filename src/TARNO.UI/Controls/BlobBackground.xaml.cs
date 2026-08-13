using System;
using System.Numerics;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Hosting;
using Microsoft.UI.Xaml.Media;
using Windows.Foundation;
using Windows.UI.ViewManagement;

namespace TARNO.UI.Controls;

/// <summary>Langsam driftende Blob-Flächen (Composition-Layer-Näherung des CSS drift-keyframes).</summary>
public sealed partial class BlobBackground : UserControl
{
    public BlobBackground()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        SizeChanged += (_, _) => UpdateClip();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        UpdateClip();

        var uiSettings = new UISettings();
        if (!uiSettings.AnimationsEnabled)
        {
            return;
        }

        AnimateDrift(Blob1, new Vector3(28f, -20f, 0f), 26);
        AnimateDrift(Blob2, new Vector3(-24f, 18f, 0f), 31);
        AnimateDrift(Blob3, new Vector3(18f, -26f, 0f), 37);
    }

    private void UpdateClip()
    {
        // WinUI panels don't clip children to their bounds by default; the
        // blobs use negative margins to bleed past the visible edge, so the
        // root needs an explicit clip or they'd render outside the sidebar.
        RootGrid.Clip = new RectangleGeometry { Rect = new Rect(0, 0, ActualWidth, ActualHeight) };
    }

    private static void AnimateDrift(FrameworkElement element, Vector3 offset, double seconds)
    {
        var visual = ElementCompositionPreview.GetElementVisual(element);
        var compositor = visual.Compositor;

        var animation = compositor.CreateVector3KeyFrameAnimation();
        var baseOffset = visual.Offset;
        animation.InsertKeyFrame(0.0f, baseOffset);
        animation.InsertKeyFrame(1.0f, baseOffset + offset);
        animation.Duration = TimeSpan.FromSeconds(seconds);
        animation.IterationBehavior = AnimationIterationBehavior.Forever;
        animation.Direction = AnimationDirection.Alternate;

        visual.StartAnimation("Offset", animation);
    }
}
