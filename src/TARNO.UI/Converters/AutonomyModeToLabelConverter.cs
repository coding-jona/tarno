using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>Maps the backend AutonomyMode string ("manual"/"balanced"/"plan"/"ultimate")
/// to its short German display label for the ChatPage mode button.</summary>
public sealed class AutonomyModeToLabelConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return (value as string) switch
        {
            "manual" => "Manuell",
            "plan" => "Plan",
            "ultimate" => "Ultimate",
            _ => "Automatisch",
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
