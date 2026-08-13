using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using Windows.UI;
using System;

namespace TARNO.UI.Converters;

/// <summary>Hebt Lead-Nachrichten in der Pool-Swimlane optisch hervor
/// (dezenter Cyan-Akzent-Hintergrund, Farbwert wie AccentPrimaryBrush/
/// ColorCyan500), Worker-Nachrichten bleiben neutral/transparent.</summary>
public sealed class BoolToPoolLeadBrushConverter : IValueConverter
{
    private static readonly SolidColorBrush LeadBrush = new(Color.FromArgb(38, 11, 199, 255));
    private static readonly SolidColorBrush WorkerBrush = new(Color.FromArgb(20, 255, 255, 255));

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value is true ? LeadBrush : WorkerBrush;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
