using Microsoft.UI.Xaml.Data;
using System;
using TARNO.UI.Helpers;

namespace TARNO.UI.Converters;

/// <summary>Maps the raw VOICE_* backend state (MainViewModel.VoiceState) to its
/// short German display label for HomePage's Voice-Statuskarte - vorher wurde der
/// rohe Enum-String (z.B. "VOICE_IDLE") unuebersetzt angezeigt. Delegiert an
/// VoiceStateLabels, die auch VoicePage.xaml.cs verwendet.</summary>
public sealed class VoiceStateToLabelConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return VoiceStateLabels.ToLabel(value as string);
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
