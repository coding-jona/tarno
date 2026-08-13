using TARNO.UI.Composition;
using TARNO.UI.Helpers;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Navigation;

namespace TARNO.UI.Pages;

public sealed partial class VoicePage : Page
{
    private MainViewModel? _viewModel;
    private bool _orbInitStarted;
    private OrbVisualController? _orbController;
    private string? _pendingState;

    public VoicePage()
    {
        this.InitializeComponent();
        // NavigationCacheMode="Required" (siehe VoicePage.xaml) hält die
        // Page-Instanz am Leben, aber Loaded feuert trotzdem bei jedem
        // Ein-/Aushängen aus dem Frame erneut (WinUI-Eigenheit, nicht an
        // Objekt-Lebensdauer gekoppelt) - der _orbInitStarted-Guard sorgt
        // dafür, dass der OrbVisualController nur einmal angehängt wird,
        // nicht bei jedem Tab-Wechsel erneut.
        Loaded += (_, _) =>
        {
            if (_orbInitStarted)
            {
                return;
            }
            _orbInitStarted = true;
            InitializeOrbComposition();
        };
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            _viewModel = vm;
            _viewModel.PropertyChanged += OnViewModelPropertyChanged;
            _viewModel.SpeechEnvelopeReceived += OnSpeechEnvelopeReceived;
            ApplyVoiceState(_viewModel.VoiceState);
            UpdateMuteStatus(_viewModel.IsVoiceMuted);
        }
        base.OnNavigatedTo(e);
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        if (_viewModel is not null)
        {
            _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
            _viewModel.SpeechEnvelopeReceived -= OnSpeechEnvelopeReceived;
        }
        base.OnNavigatedFrom(e);
    }

    private void OnSpeechEnvelopeReceived(float[] envelope, double durationSeconds)
    {
        InteractionLogger.Info("VOICE", $"OnSpeechEnvelopeReceived: envelopeLength={envelope?.Length}, duration={durationSeconds:F3}s, orbControllerNull={_orbController is null}");
        _orbController?.PlaySpeechResonance(envelope, durationSeconds);
    }

    /// <summary>
    /// Haengt den nativen Composition-Orb an (OrbGlowHost/OrbCoreHost/OrbRim
    /// aus VoicePage.xaml) - ersetzt die fruehere WebView2/CSS-Loesung, die
    /// trotz vier verschiedener, pixelverifizierter Farb-Matching-Versuche
    /// (Property, XAML, CSS, ThemeDictionary-Override) keine echte
    /// Transparenz herstellen konnte (microsoft/microsoft-ui-xaml#6527).
    /// </summary>
    private void InitializeOrbComposition()
    {
        try
        {
            _orbController = new OrbVisualController(OrbRoot, OrbGlowHost, OrbCoreHost, OrbRim);
            InteractionLogger.Info("VOICE", "Orb-Composition initialisiert.");

            if (_pendingState is { } pending)
            {
                _pendingState = null;
                _orbController.SetState(pending);
            }
        }
        catch (System.Exception ex)
        {
            InteractionLogger.Error("VOICE", $"Orb-Composition-Initialisierung fehlgeschlagen: {ex.Message}");
        }
    }

    private void OnViewModelPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (_viewModel is null)
        {
            return;
        }

        if (e.PropertyName == nameof(MainViewModel.VoiceState))
        {
            ApplyVoiceState(_viewModel.VoiceState);
        }
        else if (e.PropertyName == nameof(MainViewModel.IsVoiceMuted))
        {
            UpdateMuteStatus(_viewModel.IsVoiceMuted);
        }
        else if (e.PropertyName == nameof(MainViewModel.ThinkingState))
        {
            UpdateThinkingHint(_viewModel.ThinkingState);
        }
    }

    private void UpdateMuteStatus(bool isMuted)
    {
        MuteStatusPanel.Visibility = isMuted ? Visibility.Visible : Visibility.Collapsed;
    }

    private void UpdateThinkingHint(ThinkingViewModel thinking)
    {
        if (thinking.IsActive)
        {
            HintText.Text = thinking.Message;
        }
        else
        {
            ApplyVoiceState(_viewModel?.VoiceState ?? "VOICE_IDLE");
        }
    }

    private void ApplyVoiceState(string state)
    {
        string hint;
        bool active;
        string orbState;

        switch (state)
        {
            case "VOICE_LISTENING":
                active = true;
                orbState = "listening";
                break;
            case "VOICE_THINKING":
            case "VOICE_PROCESSING":
                active = true;
                orbState = "processing";
                break;
            case "VOICE_SPEAKING":
                active = true;
                orbState = "speaking";
                break;
            case "VOICE_ERROR":
                active = false;
                orbState = "error";
                break;
            default:
                active = MicToggle.IsChecked == true;
                orbState = active ? "listening" : "idle";
                break;
        }

        // Hint-Text: fuer bekannte Zustaende aus der gemeinsamen VoiceStateLabels-
        // Zuordnung (siehe Helpers\VoiceStateLabels.cs); der Default-Zweig braucht
        // weiterhin den aktuellen Mikrofon-Toggle-Status, den nur diese Seite kennt.
        hint = VoiceStateLabels.ToHint(state)
            ?? (active ? "TARNO hört zu..." : "Sagen Sie 'Hey Tarno' oder klicken Sie auf den Button.");

        MicToggleLabel.Text = active ? "Mikrofon deaktivieren" : "Mikrofon aktivieren";
        MicToggle.IsChecked = active;
        HintText.Text = hint;

        if (_orbController is null)
        {
            _pendingState = orbState;
        }
        else
        {
            _orbController.SetState(orbState);
        }
    }

    private async void OnMicToggleClick(object sender, RoutedEventArgs e)
    {
        if (sender is ToggleButton btn && _viewModel is not null)
        {
            var active = btn.IsChecked == true;
            InteractionLogger.Click("VoicePage", active ? "MicToggleEnable" : "MicToggleDisable");
            ApplyVoiceState(active ? "VOICE_LISTENING" : "VOICE_IDLE");
            try
            {
                await _viewModel.ToggleVoiceAsync(active);
            }
            catch (System.Exception ex)
            {
                // async void: an uncaught exception here would crash the whole app.
                InteractionLogger.Error("VOICE", $"Sprachbefehl fehlgeschlagen: {ex.Message}");
            }
        }
    }
}
