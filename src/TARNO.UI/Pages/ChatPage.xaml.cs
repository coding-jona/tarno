using TARNO.UI.Composition;
using TARNO.UI.Dialogs;
using TARNO.UI.Models;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Navigation;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Threading.Tasks;
using Windows.Storage;
using Windows.Storage.Pickers;

namespace TARNO.UI.Pages;

public sealed partial class ChatPage : Page
{
    public MainViewModel ViewModel { get; private set; } = null!;

    private bool _orbInitStarted;
    private OrbVisualController? _orbController;
    private string? _pendingOrbState;

    public ChatPage()
    {
        this.InitializeComponent();
        Loaded += (_, _) =>
        {
            if (_orbInitStarted) return;
            _orbInitStarted = true;
            InitializeOrbComposition();
        };
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            ViewModel.Messages.CollectionChanged += Messages_CollectionChanged;
            ViewModel.PropertyChanged += OnViewModelPropertyChanged;
            ViewModel.ThinkingState.PropertyChanged += OnThinkingStatePropertyChanged;
            ViewModel.SpeechEnvelopeReceived += OnSpeechEnvelopeReceived;
            ApplyVoiceState(ViewModel.VoiceState);
            Bindings.Update();
        }
        base.OnNavigatedTo(e);
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        if (ViewModel is not null)
        {
            ViewModel.Messages.CollectionChanged -= Messages_CollectionChanged;
            ViewModel.PropertyChanged -= OnViewModelPropertyChanged;
            ViewModel.ThinkingState.PropertyChanged -= OnThinkingStatePropertyChanged;
            ViewModel.SpeechEnvelopeReceived -= OnSpeechEnvelopeReceived;
        }
        base.OnNavigatedFrom(e);
    }

    /// <summary>Echte Amplituden-Huellkurve der startenden TTS-Wiedergabe -
    /// spielt die Ganzkoerper-Resonanz-Animation am Orb ab (ersetzt die
    /// fruehere, nie sichtbar gewordene Equalizer-Balken-Loesung).</summary>
    private void OnSpeechEnvelopeReceived(float[] envelope, double durationSeconds)
    {
        InteractionLogger.Info("CHAT", $"OnSpeechEnvelopeReceived: envelopeLength={envelope?.Length}, duration={durationSeconds:F3}s, orbControllerNull={_orbController is null}");
        _orbController?.PlaySpeechResonance(envelope, durationSeconds);
    }

    private void InitializeOrbComposition()
    {
        try
        {
            _orbController = new OrbVisualController(OrbRoot, OrbGlowHost, OrbCoreHost, OrbRim);
            if (_pendingOrbState is { } pending)
            {
                _pendingOrbState = null;
                _orbController.SetState(pending);
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Orb-Composition-Initialisierung fehlgeschlagen: {ex.Message}");
        }
    }

    private void OnViewModelPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MainViewModel.VoiceState))
        {
            ApplyVoiceState(ViewModel.VoiceState);
        }
    }

    /// <summary>Reacts to the real, per-stage "Denkt nach..." signal (Phase 0
    /// - ProcessingStageEvent/ThinkingUpdate) rather than only the coarse
    /// VoiceState enum. A plain text chat turn never sets VOICE_THINKING
    /// server-side (only VOICE_PROCESSING via _on_speech) - this is what
    /// actually drives the Orb into its "denkt nach"-look for a normal typed
    /// message, not just voice-conversation turns. Also reacts to StageKey
    /// changes (not just IsActive), since one turn can move through several
    /// stages - e.g. "llm_call" -&gt; "tool_exec" -&gt; "tool_followup" - while
    /// IsActive stays true the whole time; without watching StageKey too,
    /// "tool_exec" (should show Processing/purple) would never be
    /// distinguished from "llm_call" (Thinking) - found via live testing.</summary>
    private void OnThinkingStatePropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName != nameof(ThinkingViewModel.IsActive) && e.PropertyName != nameof(ThinkingViewModel.StageKey))
        {
            return;
        }

        if (ViewModel.ThinkingState.IsActive)
        {
            SetOrbState(ResolveOrbStateFromStageKey(ViewModel.ThinkingState.StageKey));
        }
        else
        {
            ApplyVoiceState(ViewModel.VoiceState);
        }
    }

    /// <summary>"tool_exec" -&gt; Processing (Datei-/Tool-Arbeit); alles andere
    /// laufende Denken (LLM-Call, Folge-Antwort, erfasstes Reasoning) -&gt;
    /// Thinking - ein eigener Orb-Zustand, nicht mehr auf "listening"
    /// gemappt (das wurde live als zu farblich ähnlich zu Idle/Speaking
    /// erkannt).</summary>
    private static string ResolveOrbStateFromStageKey(string stageKey) => stageKey switch
    {
        "tool_exec" => "processing",
        _ => "thinking",
    };

    private void ApplyVoiceState(string state)
    {
        // Waehrend eine echte Denk-Phase laeuft, hat sie Vorrang vor dem
        // groberen VoiceState-Signal (z.B. VOICE_PROCESSING, das serverseitig
        // schon vor jedem LLM-Call feuert).
        if (ViewModel.ThinkingState.IsActive)
        {
            SetOrbState(ResolveOrbStateFromStageKey(ViewModel.ThinkingState.StageKey));
            return;
        }

        var orbState = state switch
        {
            "VOICE_LISTENING" => "listening",
            "VOICE_THINKING" => "thinking",
            "VOICE_PROCESSING" => "processing",
            "VOICE_SPEAKING" => "speaking",
            "VOICE_ERROR" => "error",
            _ => "idle",
        };
        SetOrbState(orbState);
    }

    private void SetOrbState(string orbState)
    {
        if (_orbController is null)
            _pendingOrbState = orbState;
        else
            _orbController.SetState(orbState);
    }

    private void Messages_CollectionChanged(object? sender, System.Collections.Specialized.NotifyCollectionChangedEventArgs e)
    {
        if (ViewModel.Messages.Count == 0)
        {
            return;
        }
        // ScrollIntoView (unlike ScrollViewer.ChangeView + ScrollableHeight)
        // works correctly even before ListView has finished measuring the
        // newly-added item, and doesn't fight with the list's own
        // virtualization the way the previous ItemsRepeater setup did.
        MessagesListView.ScrollIntoView(ViewModel.Messages[^1]);
    }

    private void OnSendClick(object sender, RoutedEventArgs e)
    {
        if (ViewModel.IsBusy)
        {
            CancelMessage();
        }
        else
        {
            SendMessage();
        }
    }

    private void OnChatInputKeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key != Windows.System.VirtualKey.Enter)
        {
            return;
        }
        // Shift+Enter inserts a newline (default TextBox behavior with
        // AcceptsReturn) so pasted/typed multi-paragraph text works. Plain
        // Enter sends, matching the usual chat-app convention.
        var shiftDown = Microsoft.UI.Input.InputKeyboardSource
            .GetKeyStateForCurrentThread(Windows.System.VirtualKey.Shift)
            .HasFlag(Windows.UI.Core.CoreVirtualKeyStates.Down);
        if (shiftDown)
        {
            return;
        }
        if (!ViewModel.IsBusy)
        {
            SendMessage();
        }
        e.Handled = true;
    }

    private async void SendMessage()
    {
        var text = ChatInput.Text?.Trim();
        if (string.IsNullOrEmpty(text))
        {
            return;
        }
        InteractionLogger.Click("ChatPage", "SendMessage");
        InteractionLogger.Info("CHAT", $"User message sent: {text}");
        ChatInput.Text = string.Empty;
        try
        {
            await ViewModel.SendChatMessageAsync(text);
        }
        catch (Exception ex)
        {
            // async void: an uncaught exception here would crash the whole
            // app instead of just failing this one message.
            InteractionLogger.Error("CHAT", $"Nachricht konnte nicht gesendet werden: {ex.Message}");
        }
    }

    private async void OnAutonomyModeManual(object sender, RoutedEventArgs e) => await SetAutonomyModeAsync("manual");
    private async void OnAutonomyModeBalanced(object sender, RoutedEventArgs e) => await SetAutonomyModeAsync("balanced");
    private async void OnAutonomyModePlan(object sender, RoutedEventArgs e) => await SetAutonomyModeAsync("plan");
    private async void OnAutonomyModeUltimate(object sender, RoutedEventArgs e) => await SetAutonomyModeAsync("ultimate");

    private async Task SetAutonomyModeAsync(string mode)
    {
        InteractionLogger.Click("ChatPage", $"AutonomyMode:{mode}");
        try
        {
            await ViewModel.SetAutonomyModeAsync(mode);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Autonomie-Modus konnte nicht gesetzt werden: {ex.Message}");
        }
    }

    /// <summary>Phase 1-6: befuellt jedes Provider-Untermenue neu bei jedem
    /// Oeffnen - ein "Standard"-Eintrag (Provider-Default) gefolgt von den
    /// kuratierten Modellen aus ViewModel.ModelCatalog, jeweils mit Rate-
    /// Limit-Schaetzung und Faehigkeits-Stichworten in der Beschriftung.</summary>
    private async void OnProviderFlyoutOpening(object? sender, object e)
    {
        if (ViewModel.ModelCatalog.Count == 0)
        {
            try
            {
                await ViewModel.LoadModelCatalogAsync();
            }
            catch (Exception ex)
            {
                InteractionLogger.Error("CHAT", $"Modellkatalog konnte nicht geladen werden: {ex.Message}");
            }
        }
        PopulateModelSubItem(MistralModelsSubItem, "mistral");
        PopulateModelSubItem(OpenAIModelsSubItem, "openai");
        PopulateModelSubItem(ClaudeModelsSubItem, "claude");
        PopulateModelSubItem(GeminiModelsSubItem, "gemini");
        PopulateModelSubItem(GroqModelsSubItem, "groq");
        PopulateModelSubItem(HuggingFaceModelsSubItem, "huggingface");
        PopulateModelSubItem(GlmModelsSubItem, "glm");
        PopulateModelSubItem(PerplexityModelsSubItem, "perplexity");
        PopulateModelSubItem(MetaModelsSubItem, "meta");
        PopulateModelSubItem(DeepSeekModelsSubItem, "deepseek");
        PopulateModelSubItem(MoonshotModelsSubItem, "moonshot");
        PopulateModelSubItem(QwenModelsSubItem, "qwen");
        PopulateModelSubItem(OpenRouterModelsSubItem, "openrouter");
        PopulateModelSubItem(OllamaModelsSubItem, "ollama");
    }

    private void PopulateModelSubItem(MenuFlyoutSubItem subItem, string provider)
    {
        subItem.Items.Clear();

        var standardItem = new MenuFlyoutItem { Text = "Standard" };
        standardItem.Click += async (_, _) => await SetProviderAsync(provider, null);
        subItem.Items.Add(standardItem);

        if (ViewModel.ModelCatalog.TryGetValue(provider, out var models) && models.Count > 0)
        {
            subItem.Items.Add(new MenuFlyoutSeparator());
            foreach (var model in models)
            {
                var label = string.IsNullOrEmpty(model.RateLimitNote)
                    ? $"{model.Label} ({model.Capabilities})"
                    : $"{model.Label} — {model.RateLimitNote} ({model.Capabilities})";
                var item = new MenuFlyoutItem { Text = label };
                var modelId = model.Id;
                item.Click += async (_, _) => await SetProviderAsync(provider, modelId);
                subItem.Items.Add(item);
            }
        }
    }

    private async Task SetProviderAsync(string provider, string? model)
    {
        InteractionLogger.Click("ChatPage", $"Provider:{provider}" + (string.IsNullOrEmpty(model) ? "" : $"/{model}"));
        try
        {
            await ViewModel.SetProviderAsync(provider, model);
            if (!string.IsNullOrEmpty(ViewModel.ProviderSwitchError))
            {
                InteractionLogger.Error("CHAT", $"Provider-Wechsel fehlgeschlagen: {ViewModel.ProviderSwitchError}");
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Provider-Wechsel fehlgeschlagen: {ex.Message}");
        }
    }

    private async void OnReasoningToggleClick(object sender, RoutedEventArgs e)
    {
        var newState = !ViewModel.ReasoningModeEnabled;
        InteractionLogger.Click("ChatPage", $"ReasoningToggle:{newState}");
        try
        {
            await ViewModel.SetReasoningModeAsync(newState, "medium");
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Denk-Modus-Umschaltung fehlgeschlagen: {ex.Message}");
        }
    }

    private async void OnHighTierToggleClick(object sender, RoutedEventArgs e)
    {
        var newState = !ViewModel.HighTierModelEnabled;
        InteractionLogger.Click("ChatPage", $"HighTierToggle:{newState}");
        try
        {
            await ViewModel.SetHighTierModelAsync(newState);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Starkes-Modell-Umschaltung fehlgeschlagen: {ex.Message}");
        }
    }

    private async void OnVisionToggleClick(object sender, RoutedEventArgs e)
    {
        // Muss von VisionCameraActive ausgehen, nicht VisionEnabledByUser:
        // der Button zeigt VisionCameraActive an (Zeile 175/177 im XAML) und
        // VisionEnabledByUser startet mit einem abweichenden Default (true)
        // - dadurch berechnete der erste Klick nach App-Start ein falsches
        // Ziel (!true = false, ein No-Op, da die Kamera noch nie an war) und
        // der Button wirkte komplett wirkungslos.
        var newState = !ViewModel.VisionCameraActive;
        InteractionLogger.Click("ChatPage", $"VisionToggle:{newState}");
        string connectionBefore = ViewModel.ConnectionStatus;
        try
        {
            await ViewModel.SetVisionEnabledAsync(newState);
            // TEMPORAERE DIAGNOSE (siehe Chat-Verlauf 2026-07-31): das
            // ui_interactions.log fuellt sich seit Stunden nicht mehr,
            // obwohl der Klick laut Nutzer registriert wird - dieser Dialog
            // umgeht die Logdatei komplett und zeigt den Zustand direkt in
            // der UI, um zu klaeren, ob der Handler ueberhaupt durchlaeuft
            // und ob die gRPC-Verbindung zum Zeitpunkt des Klicks stand.
            var dialog = new ContentDialog
            {
                Title = "Vision-Diagnose",
                Content = $"Angefordert: {newState}\nVerbindung (vorher): {connectionBefore}\nVerbindung (jetzt): {ViewModel.ConnectionStatus}\nVisionCameraActive: {ViewModel.VisionCameraActive}\nVisionAvailable: {ViewModel.VisionAvailable}",
                CloseButtonText = "OK",
                XamlRoot = this.XamlRoot,
            };
            await dialog.ShowAsync();
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("VISION", $"Kamera-Umschaltung fehlgeschlagen: {ex.Message}");
            try
            {
                var errorDialog = new ContentDialog
                {
                    Title = "Vision-Diagnose (Fehler)",
                    Content = ex.ToString(),
                    CloseButtonText = "OK",
                    XamlRoot = this.XamlRoot,
                };
                await errorDialog.ShowAsync();
            }
            catch
            {
                // Best-effort: Diagnose-Dialog darf nicht selbst crashen.
            }
        }
    }

    private async void OnOpenChatSettingsClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("ChatPage", "OpenChatSettingsDialog");
        var dialog = new ChatSettingsDialog(ViewModel)
        {
            XamlRoot = this.XamlRoot,
        };
        await dialog.ShowAsync();
    }

    /// <summary>Phase A: Bild-Anhang für die nächste Chat-Nachricht auswählen.
    /// Der FileTypeFilter lässt gar keine Nicht-Bilddateien zur Auswahl zu -
    /// einfacher und robuster als eine nachträgliche MIME-Prüfung mit
    /// Fehlermeldung.</summary>
    private async void OnAttachClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("ChatPage", "Attach");
        try
        {
            var picker = new FileOpenPicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(App.MainWindow);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.FileTypeFilter.Add(".jpg");
            picker.FileTypeFilter.Add(".jpeg");
            picker.FileTypeFilter.Add(".png");
            picker.FileTypeFilter.Add(".webp");

            StorageFile? file = await picker.PickSingleFileAsync();
            if (file is null)
            {
                return;
            }

            var buffer = await FileIO.ReadBufferAsync(file);
            var bytes = buffer.ToArray();
            var mimeType = string.IsNullOrEmpty(file.ContentType) ? "image/jpeg" : file.ContentType;
            await ViewModel.SetPendingAttachmentAsync(bytes, file.Name, mimeType);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Bild-Auswahl fehlgeschlagen: {ex.Message}");
        }
    }

    private void OnRemoveAttachmentClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("ChatPage", "RemoveAttachment");
        ViewModel.ClearPendingAttachment();
    }

    /// <summary>Phase B: einmaliges Diktat für dieses Chat-Textfeld. Blockiert
    /// den Button (kein Doppel-Klick) bis die Antwort da ist - kein neuer
    /// Orb-Zustand nötig, der Button selbst zeigt "..." während der Aufnahme.</summary>
    private async void OnDictateClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("ChatPage", "Dictate");
        DictateButton.IsEnabled = false;
        DictateButton.Content = "...";
        try
        {
            var eagerness = ViewModel.Settings.DictateEagerness;
            var (success, text, error) = await ViewModel.DictateAsync(eagerness);
            if (success)
            {
                ChatInput.Text = text;
                ChatInput.SelectionStart = ChatInput.Text.Length;
                ChatInput.Focus(FocusState.Programmatic);
            }
            else
            {
                InteractionLogger.Error("CHAT", $"Diktat fehlgeschlagen: {error}");
                await ShowTransientDictateErrorAsync(error);
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Diktat fehlgeschlagen: {ex.Message}");
        }
        finally
        {
            DictateButton.Content = "🎙";
            DictateButton.IsEnabled = true;
        }
    }

    /// <summary>Zeigt einen Diktat-Fehler kurz als Placeholder-Text im leeren
    /// Chat-Textfeld an - kein neues InfoBar-Element nötig, da nirgendwo
    /// sonst im Projekt verwendet.</summary>
    private async Task ShowTransientDictateErrorAsync(string error)
    {
        var original = ChatInput.PlaceholderText;
        ChatInput.PlaceholderText = $"⚠ {error}";
        await Task.Delay(TimeSpan.FromSeconds(4));
        if (ChatInput.PlaceholderText == $"⚠ {error}")
        {
            ChatInput.PlaceholderText = original;
        }
    }

    private async void CancelMessage()
    {
        InteractionLogger.Click("ChatPage", "CancelMessage");
        try
        {
            await ViewModel.CancelCurrentChatAsync();
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Abbrechen fehlgeschlagen: {ex.Message}");
        }
    }

    private void OnTraceToggleClick(object sender, RoutedEventArgs e)
    {
        bool show = TracePanel.Visibility == Visibility.Collapsed;
        TracePanel.Visibility = show ? Visibility.Visible : Visibility.Collapsed;
    }

    private void OnCodingActionModeClick(object sender, RoutedEventArgs e)
    {
        // Flyout oeffnet sich automatisch.
    }

    private void OnActionModePlan(object sender, RoutedEventArgs e)
    {
        ViewModel.CodingActionMode = ActionMode.Plan;
    }

    private void OnActionModeManual(object sender, RoutedEventArgs e)
    {
        ViewModel.CodingActionMode = ActionMode.Manual;
    }

    private void OnActionModeAuto(object sender, RoutedEventArgs e)
    {
        ViewModel.CodingActionMode = ActionMode.Auto;
    }

}
