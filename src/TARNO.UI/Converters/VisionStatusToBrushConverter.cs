using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using System;
using Windows.UI;

namespace TARNO.UI.Converters;

/// <summary>Block 7, Phase 69: Kamera-Status-Farbe. Rot leuchtend nur wenn
/// die Kamera-Hardware tatsächlich aktiv erfasst (Wert von
/// ViewModel.VisionCameraActive) - bewusst auffällig, da dies der einzige
/// UI-Indikator dafür ist, dass gerade Bilddaten erfasst werden.</summary>
public sealed class VisionStatusToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value is true
            ? new SolidColorBrush(Color.FromArgb(255, 255, 68, 68))   // aktiv: Warnrot
            : new SolidColorBrush(Color.FromArgb(255, 136, 144, 164)); // aus/inaktiv: gedämpftes Grau
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
