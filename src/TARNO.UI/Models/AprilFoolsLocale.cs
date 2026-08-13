using System.Text.Json.Serialization;

namespace TARNO.UI.Models;

/// <summary>
/// Deutsche Voice-Lines und Audio-Dateien für den April-Fools-Modus.
/// Wird aus Assets/AprilFools/locales/de_april_fools.json geladen.
/// </summary>
public class AprilFoolsLocale
{
    [JsonPropertyName("closeButton")]
    public AprilFoolsCloseButtonLocale CloseButton { get; set; } = new();

    [JsonPropertyName("taskbarClose")]
    public AprilFoolsSimpleLocale TaskbarClose { get; set; } = new();

    [JsonPropertyName("forceQuit")]
    public AprilFoolsSimpleLocale ForceQuit { get; set; } = new();

    [JsonPropertyName("mainButtonClick")]
    public AprilFoolsMainButtonLocale MainButtonClick { get; set; } = new();

    [JsonPropertyName("monitorDrag")]
    public AprilFoolsSimpleLocale MonitorDrag { get; set; } = new();

    [JsonPropertyName("keyboardStress")]
    public AprilFoolsSimpleLocale KeyboardStress { get; set; } = new();
}

public class AprilFoolsCloseButtonLocale
{
    [JsonPropertyName("stage1Tooltip")]
    public string Stage1Tooltip { get; set; } = "Versuch's gar nicht erst.";

    [JsonPropertyName("stage1Audio")]
    public string Stage1Audio { get; set; } = "close_evade_1.wav";

    [JsonPropertyName("stage2Tooltip")]
    public string Stage2Tooltip { get; set; } = "Zu langsam!";

    [JsonPropertyName("stage2Audio")]
    public string Stage2Audio { get; set; } = "close_evade_2.wav";

    [JsonPropertyName("stage3Tooltip")]
    public string Stage3Tooltip { get; set; } = "Welches X ist das echte?";

    [JsonPropertyName("stage3Audio")]
    public string Stage3Audio { get; set; } = "close_evade_3.wav";

    [JsonPropertyName("fakeClickAudio")]
    public string FakeClickAudio { get; set; } = "glitch_click.wav";
}

public class AprilFoolsSimpleLocale
{
    [JsonPropertyName("audio")]
    public string Audio { get; set; } = string.Empty;

    [JsonPropertyName("toast")]
    public string Toast { get; set; } = string.Empty;

    [JsonPropertyName("voiceLine")]
    public string VoiceLine { get; set; } = string.Empty;
}

public class AprilFoolsMainButtonLocale
{
    [JsonPropertyName("toast")]
    public string Toast { get; set; } = "Heute im Streik.";

    [JsonPropertyName("audio")]
    public string Audio { get; set; } = "blue_monday.wav";
}
