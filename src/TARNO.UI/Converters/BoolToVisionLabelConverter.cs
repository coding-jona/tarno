using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>Block 7, Phase 69: Text für den Kamera-Status-Indikator.</summary>
public sealed class BoolToVisionLabelConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value is true ? "Kamera aktiv" : "Kamera aus";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
