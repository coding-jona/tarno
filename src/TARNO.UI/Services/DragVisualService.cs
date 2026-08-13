using System;
using System.Threading.Tasks;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Graphics.Imaging;

namespace TARNO.UI.Services;

/// <summary>
/// Erzeugt ein Bitmap-Drag-Visual für ein UI-Element, damit beim
/// Drag-and-Drop nicht nur der kleine Header, sondern das gesamte
/// Element als Vorschau angezeigt wird.
/// </summary>
public static class DragVisualService
{
    public static async Task SetDragVisualAsync(DragStartingEventArgs e, FrameworkElement element)
    {
        var deferral = e.GetDeferral();
        try
        {
            if (element.ActualWidth <= 0 || element.ActualHeight <= 0)
            {
                return;
            }

            var renderTarget = new RenderTargetBitmap();
            await renderTarget.RenderAsync(element);

            var buffer = await renderTarget.GetPixelsAsync();
            using var softwareBitmap = SoftwareBitmap.CreateCopyFromBuffer(
                buffer,
                BitmapPixelFormat.Bgra8,
                renderTarget.PixelWidth,
                renderTarget.PixelHeight,
                BitmapAlphaMode.Premultiplied);

            e.DragUI.SetContentFromSoftwareBitmap(softwareBitmap);
        }
        catch
        {
            // Fallback: Standard-Drag-Visual.
        }
        finally
        {
            deferral.Complete();
        }
    }
}
