using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using System;
using Windows.UI;

namespace TARNO.UI.Converters;

/// <summary>Gibt dem "Ultimate"-Modus (bypasst auch die HIGH-Sicherheitsphrase) eine
/// auffällige Warnfarbe statt des sonstigen Cyan-Akzents der übrigen Modi.</summary>
public sealed class AutonomyModeToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value as string == "ultimate"
            ? new SolidColorBrush(Color.FromArgb(255, 255, 107, 53))   // Warnorange
            : new SolidColorBrush(Color.FromArgb(255, 11, 199, 255));  // Standard-Akzent
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
