using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>Generisches An/Aus-Label für Bool-Umschalter. ConverterParameter
/// legt das Label-Präfix fest (z.B. "Denken", "Starkes Modell") - ohne
/// Parameter bleibt "Denken" der Standard (Abwärtskompatibilität mit dem
/// ursprünglichen Denk-Modus-Umschalter).
///
/// Gefunden live: der Denken-Umschalter UND der Starkes-Modell-Umschalter
/// nutzten denselben, fest auf "Denken" verdrahteten Converter - beide
/// zeigten "Denken: An/Aus" an, obwohl der zweite Schalter überhaupt nichts
/// mit dem Reasoning-Modus zu tun hat (steuert HighTierModelEnabled).</summary>
public sealed class BoolToOnOffLabelConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        string label = parameter as string ?? "Denken";
        return value is true ? $"{label}: An" : $"{label}: Aus";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
