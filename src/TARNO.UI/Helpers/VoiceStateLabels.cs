using System;

namespace TARNO.UI.Helpers;

/// <summary>Einzige Quelle fuer die Zuordnung der rohen VOICE_*-Zustaende
/// (aus MainViewModel.VoiceState, letztlich von GrpcClientService.cs
/// durchgereicht) auf deutsche Anzeigetexte. Vorher dreifach dupliziert
/// (VoicePage.xaml.cs/ChatPage.xaml.cs hatten je einen eigenen switch,
/// HomePage.xaml zeigte den rohen Enum-String gar nicht erst gemappt an) -
/// jetzt ein Ort fuer die beiden tatsaechlich wiederverwendbaren Teile
/// (kurzes Karten-Label, voller Hinweistext). Zustandsabhaengige Logik, die
/// NICHT rein vom State-String abhaengt (z.B. VoicePage's Default-Zweig, der
/// den aktuellen MicToggle-Status braucht, oder ChatPage's abweichendes
/// Thinking/Processing-Mapping fuer den Orb), bleibt bewusst dort, wo sie
/// steht - siehe Aufrufer.</summary>
public static class VoiceStateLabels
{
    /// <summary>Kurzes Label fuer Statuskarten (z.B. HomePage-Voice-Kachel).</summary>
    public static string ToLabel(string? state) => state switch
    {
        "VOICE_LISTENING" => "Hört zu",
        "VOICE_THINKING" or "VOICE_PROCESSING" => "Denkt nach",
        "VOICE_SPEAKING" => "Spricht",
        "VOICE_ERROR" => "Fehler",
        _ => "Bereit",
    };

    /// <summary>Voller Hinweissatz fuer die bekannten VOICE_*-Zustaende (wie bisher
    /// in VoicePage.xaml.cs). Gibt null fuer unbekannte/Default-Zustaende zurueck -
    /// der Aufrufer entscheidet dort selbst (z.B. abhaengig vom Mikrofon-Toggle),
    /// keine falsche Pauschalantwort von hier aus.</summary>
    public static string? ToHint(string? state) => state switch
    {
        "VOICE_LISTENING" => "TARNO hört zu...",
        "VOICE_THINKING" or "VOICE_PROCESSING" => "TARNO denkt nach...",
        "VOICE_SPEAKING" => "TARNO spricht...",
        "VOICE_ERROR" => "Es ist ein Fehler aufgetreten.",
        _ => null,
    };
}
