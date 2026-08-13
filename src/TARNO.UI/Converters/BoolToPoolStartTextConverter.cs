using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>True (Pool-Lauf läuft) -> "Läuft...", false -> "Pool starten".</summary>
public sealed class BoolToPoolStartTextConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value is true ? "Läuft..." : "Pool starten";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
