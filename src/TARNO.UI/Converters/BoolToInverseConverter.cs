using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>Negiert einen bool - z.B. um IsEnabled aus einem "läuft gerade"-Flag abzuleiten.</summary>
public sealed class BoolToInverseConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return !(value is true);
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        return !(value is true);
    }
}
