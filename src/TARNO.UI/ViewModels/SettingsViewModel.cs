using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;

namespace TARNO.UI.ViewModels;

/// <summary>
/// UI-facing settings. Values are persisted to disk by the consuming page.
/// Does not itself touch the filesystem to keep the ViewModel testable.
/// </summary>
public partial class SettingsViewModel : ObservableObject
{
    [ObservableProperty]
    private string _theme = "Dark";

    /// <summary>Sprache der UI und der Spracherkennung (de | en).</summary>
    [ObservableProperty]
    private string _language = "de";

    public ObservableCollection<string> AvailableLanguages { get; } = new() { "de", "en" };

    [ObservableProperty]
    private AppPage _startupPage = AppPage.Home;

    [ObservableProperty]
    private bool _autoStart;

    [ObservableProperty]
    private string _microphoneDevice = "default";

    /// <summary>Vom Backend enumerierte Mikrofon-Geraete (echte Namen, inkl.
    /// eingebauter Array-Mikrofone) - populiert per GetMicrophoneDevicesAsync
    /// beim Oeffnen der Settings-Seite, ersetzt das statische "Windows
    /// 10/11"-Auswahlkonzept (recherchiert und verworfen: keine echte
    /// OS-Versions-abhaengige API-Differenz, siehe Plan).</summary>
    public ObservableCollection<string> AvailableMicrophoneDevices { get; } = new();

    [ObservableProperty]
    private string _speakerDevice = "default";

    /// <summary>Vom Backend enumerierte Lautsprecher-/Ausgabegeraete (via
    /// pygame/SDL2), populiert per GetSpeakerDevicesAsync.</summary>
    public ObservableCollection<string> AvailableSpeakerDevices { get; } = new();

    /// <summary>Bestätigungston beim Wake-Word-Trigger (entspricht config.wakeword.confirm_wake_word im Python-Backend).</summary>
    [ObservableProperty]
    private bool _wakeWordConfirmSound = true;

    /// <summary>Ob der First-Start-Wizard (API-Key-Abfrage) bereits gezeigt/abgeschlossen wurde.</summary>
    [ObservableProperty]
    private bool _firstRunWizardCompleted;

    /// <summary>Phase B (In-Chat-Diktat): "low" | "medium" | "high" - steuert
    /// wie geduldig die Stille-Erkennung beim Diktieren ist (entspricht
    /// vad_config_for_eagerness im Python-Backend, per Dictate-RPC-Parameter
    /// übergeben, nicht serverseitig persistiert).</summary>
    [ObservableProperty]
    private string _dictateEagerness = "medium";

    /// <summary>Basis-URL des Tarno-Servers (siehe tarno-server/README.md).
    /// KERNFIX: war "http://127.0.0.1:8000" (lokaler Test-Default aus der
    /// Zeit vor der VPS-Migration) - dieser Wert blieb ueber die geteilte
    /// %LOCALAPPDATA%\TARNO\settings.json auch in frischen Installationen
    /// haengen. Jetzt direkt die echte Produktions-Domain als Default, und
    /// NICHT mehr per App-UI aenderbar (siehe MeshDevicesPage.xaml) - nur
    /// noch per direkter Bearbeitung der settings.json.</summary>
    [ObservableProperty]
    private string _meshServerUrl = "https://tarno.cousinsmp.de";

    /// <summary>Global hotkey for toggling the microphone mute state.
    /// Format "Ctrl+Alt+Key", e.g. "Ctrl+Alt+M". Empty means disabled.</summary>
    [ObservableProperty]
    private string _muteHotkey = "Ctrl+Alt+M";

    // Multi-Screen / Lochbrett
    [ObservableProperty]
    private bool _multiScreenEnabled;

    [ObservableProperty]
    private bool _autoScreenSplit = true;

    [ObservableProperty]
    private int _manualScreenCount = 1;

    [ObservableProperty]
    private string _activeLayoutProfile = "Standard";

    /// <summary>Lochbrett-Modus aktiv: SnapCanvas-Drag, Resize und Pop-Out.</summary>
    [ObservableProperty]
    private bool _pegboardEnabled = true;

    /// <summary>Pixel pro Gitterzelle für den Lochbrett-Canvas.</summary>
    [ObservableProperty]
    private int _snapGridSize = 24;

    /// <summary>Entwickler-Schalter für den April-Fools-Burnout-Modus.</summary>
    [ObservableProperty]
    private bool _aprilFoolsEnabled;
}
