using CommunityToolkit.Mvvm.ComponentModel;
using Grpc.Core;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using TARNO.Grpc;
using TARNO.UI.Models;
using TARNO.UI.Services;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Threading.Tasks;
using Windows.Globalization;
using Windows.Storage.Streams;
using Windows.UI;

namespace TARNO.UI.ViewModels;

public enum AppPage
{
    Home,
    Voice,
    Chat,
    Tasks,
    Memory,
    Settings,
    ApiKeys,
    Logs,
    Workspaces,
    Code,
    MeshDevices,
    MeshDashboard
}

public enum SidebarMode
{
    Chat,
    Code
}

public partial class MainViewModel : ObservableObject
{
    private readonly GrpcClientService _grpcClient;

    [ObservableProperty]
    private AppPage _selectedPage = AppPage.Home;

    [ObservableProperty]
    private SidebarMode _selectedSidebarMode = SidebarMode.Chat;

    [ObservableProperty]
    private string _connectionStatus = "Offline";

    [ObservableProperty]
    private string _statusText = "Bereit";

    [ObservableProperty]
    private string _systemInfo = "—";

    /// <summary>Aktueller Voice-Pipeline-Zustand: VOICE_IDLE / VOICE_LISTENING / VOICE_THINKING.</summary>
    [ObservableProperty]
    private string _voiceState = "VOICE_IDLE";

    /// <summary>True when the microphone is explicitly muted/idle and the
    /// hotkey has not turned voice listening on. Drives the visible mute
    /// indicator in VoicePage and the footer status text.</summary>
    [ObservableProperty]
    private bool _isVoiceMuted = true;

    /// <summary>Aktueller Autonomie-Modus (entspricht AutonomyMode im Python-Backend):
    /// "manual" | "balanced" | "plan" | "ultimate". Steuert, wie viel TARNO ohne
    /// Rückfrage ausführen darf.</summary>
    [ObservableProperty]
    private string _autonomyMode = "balanced";

    /// <summary>Phase C: "Denk-Modus" - fordert aktiv strukturierten Denk-
    /// Inhalt vom LLM an (kostet mehr Tokens/Latenz). NUR aus dem Server-
    /// Echo gesetzt, nie optimistisch beim Klick.</summary>
    [ObservableProperty]
    private bool _reasoningModeEnabled;

    [ObservableProperty]
    private string _reasoningEffort = "medium";

    /// <summary>Phase D: aktiver LLM-Provider - NUR aus dem Server-Echo
    /// gesetzt (auch bei fehlgeschlagenem Wechsel, dann bleibt es der
    /// weiterhin aktive alte Provider), nie optimistisch beim Klick.</summary>
    [ObservableProperty]
    private string _activeProvider = "mistral";

    [ObservableProperty]
    private string? _providerSwitchError;

    /// <summary>Phase 1-6: aktives Modell des aktiven Providers (leer = Provider-
    /// Standard). NUR aus dem Server-Echo gesetzt, wie ActiveProvider.</summary>
    [ObservableProperty]
    private string _activeModel = string.Empty;

    public string ActiveProviderModelLabel =>
        string.IsNullOrWhiteSpace(ActiveModel) ? ActiveProvider : $"{ActiveProvider} › {ActiveModel}";

    partial void OnActiveProviderChanged(string value) => OnPropertyChanged(nameof(ActiveProviderModelLabel));
    partial void OnActiveModelChanged(string value) => OnPropertyChanged(nameof(ActiveProviderModelLabel));

    /// <summary>Phase 1-6: kuratierter Modell-Katalog pro Provider (Label,
    /// Rate-Limit-Schätzung, Fähigkeits-Stichworte) für den Modell-Picker.
    /// "ollama" wird dynamisch vom Backend befüllt (lokal installierte Modelle).</summary>
    public Dictionary<string, List<ModelOptionViewModel>> ModelCatalog { get; } = new();

    /// <summary>Agent-Pool: alle waehlbaren Provider/Modell-Paare aus dem
    /// bestehenden ModelCatalog, flach als auswaehlbare Liste fuer den
    /// Mehrfachauswahl-Dialog (siehe PoolAgentPickerDialog). Neu befuellt
    /// bei jedem LoadModelCatalogAsync-Aufruf.</summary>
    public ObservableCollection<PoolAgentSelectionItem> PoolAgentCatalog { get; } = new();

    /// <summary>true, waehrend im Chat-Header der Agent-Pool-Modus statt
    /// Einzel-Agent-Modus aktiv ist (Umschalter in ChatPage.xaml.cs -
    /// OnPoolModeToggleClick). Rein lokaler UI-Zustand, kein
    /// Server-Roundtrip, da der Pool selbst keinen dauerhaften
    /// Backend-Zustand hat.</summary>
    [ObservableProperty]
    private bool _isPoolModeEnabled;

    /// <summary>Live-Swimlane-Transkript des zuletzt/gerade laufenden
    /// Agent-Pool-Laufs.</summary>
    public ObservableCollection<PoolMessageDisplay> PoolTranscript { get; } = new();

    /// <summary>Pro-Agent-Statuskarten fuer die Live-Ansicht im Code-Workspace
    /// (Vorbild: Claude Codes Hintergrundaufgaben-Kartenliste) - rein aus
    /// PoolTranscript-Ereignissen abgeleitet, ein Eintrag pro am aktuellen
    /// Lauf beteiligtem Agent.</summary>
    public ObservableCollection<PoolAgentStatusDisplay> PoolAgentStatuses { get; } = new();

    [ObservableProperty]
    private bool _isPoolTaskRunning;

    /// <summary>Manueller "Starkes Modell"-Schalter (Mistral mistral-medium-2508,
    /// ersetzt die vormals automatische, fehleranfaellige Klassifizierung) -
    /// NUR aus dem Server-Echo gesetzt.</summary>
    [ObservableProperty]
    private bool _highTierModelEnabled;

    /// <summary>Chat-Umschalter "Vorlesen": true = Antworten werden per TTS
    /// vorgelesen (bisheriges Verhalten), false = Chat läuft rein textuell
    /// ohne auf die Sprachwiedergabe warten zu müssen - NUR aus dem
    /// Server-Echo gesetzt. Default true, weil das Backend selbst mit
    /// speak_responses_enabled=True startet und nie unaufgefordert einen
    /// initialen Echo-Zustand sendet.</summary>
    [ObservableProperty]
    private bool _speakResponsesEnabled = true;

    /// <summary>Chat-Umschalter "Kontext-Effizienz" (Beta): Tool-Output-
    /// Kompression + rekursive Verlauf-Zusammenfassung im normalen Chat-Modus
    /// - NUR aus dem Server-Echo gesetzt. Default false (matcht das
    /// Backend-Config-Default context_efficiency.enabled=False).</summary>
    [ObservableProperty]
    private bool _contextEfficiencyEnabled;

    /// <summary>Block 7, Phase 69: spiegelt echte Kamera-Hardware-Aktivität
    /// wider (nicht nur den Enabled-Flag) - true genau dann, wenn die
    /// physische Kamera-LED leuchten sollte.</summary>
    [ObservableProperty]
    private bool _visionCameraActive;

    /// <summary>False wenn Vision im Backend deaktiviert ist, kein API-Key
    /// konfiguriert ist, oder keine Kamera gefunden wurde.</summary>
    [ObservableProperty]
    private bool _visionAvailable;

    /// <summary>Nutzer-Opt-out-Zustand (unabhängig von VisionAvailable) -
    /// true = Nutzer hat die Kamera nicht manuell deaktiviert.</summary>
    [ObservableProperty]
    private bool _visionEnabledByUser = true;

    public ObservableCollection<ChatMessageViewModel> Messages { get; } = new();
    public ObservableCollection<LogEntryViewModel> Logs { get; } = new();
    public ObservableCollection<TaskViewModel> Tasks { get; } = new();
    public ObservableCollection<MemoryFactViewModel> MemoryFacts { get; } = new();
    public ObservableCollection<MemoryEpisodeViewModel> MemoryEpisodes { get; } = new();
    public ObservableCollection<TARNO.UI.Models.Workspace> Workspaces { get; } = new();
    public ObservableCollection<AgentTraceViewModel> TraceItems { get; } = new();
    public ObservableCollection<string> CodingOutputs { get; } = new();
    public ObservableCollection<string> SelectedContextFiles { get; } = new();
    public ObservableCollection<ChatSessionViewModel> ChatSessions { get; } = new();
    public ObservableCollection<ChatSessionViewModel> FilteredChatSessions { get; } = new();

    /// <summary>Aktuell geladene Chat-Sitzung inkl. Nachrichten.</summary>
    private ChatSession _activeSession = new();

    [ObservableProperty]
    private ChatSessionViewModel? _selectedChatSession;

    [ObservableProperty]
    private TARNO.UI.Models.Workspace? _selectedWorkspace;

    /// <summary>Action-Modus des Coding-Agenten: Plan (nur Vorschläge),
    /// Manual (immer fragen), Auto (innerhalb Workspace sofort ausführen).</summary>
    [ObservableProperty]
    private ActionMode _codingActionMode = ActionMode.Manual;

    /// <summary>False wenn das Gedächtnis-Modul im Backend deaktiviert ist
    /// (config.memory.enabled=false) oder die Mock-Engine läuft.</summary>
    [ObservableProperty]
    private bool _memoryEnabled;

    [ObservableProperty]
    private ThinkingViewModel _thinkingState = new();

    /// <summary>True while a chat request is in flight (waiting for the assistant's
    /// answer) - drives the Send/Stop button toggle in ChatPage.</summary>
    [ObservableProperty]
    private bool _isBusy;

    [ObservableProperty]
    private int _contextUsedTokens;

    [ObservableProperty]
    private int _contextMaxTokens = 32000;

    /// <summary>0-100, for the token-usage ring indicator. 0 until the backend
    /// reports real usage from the first response (no client-side estimate).</summary>
    public double ContextUsagePercent =>
        ContextMaxTokens > 0 ? Math.Min(100.0, 100.0 * ContextUsedTokens / ContextMaxTokens) : 0;

    [ObservableProperty]
    private SettingsViewModel _settings;

    private bool _hasConnectedOnce;
    private bool _isSelectingChat;

    /// <summary>Puffer für Vision-Bilder, die vor der zugehörigen
    /// Assistant-Text-Nachricht eintreffen. Wird in OnGrpcMessageReceived
    /// an die nächste Assistant-Nachricht angehängt.</summary>
    private ImageSource? _pendingVisionImageSource;
    private string? _pendingVisionCaption;
    private string? _streamingResponseTraceId;
    private readonly AppState _uiState;

    /// <summary>Phase A: vom Datei-Picker ausgewähltes, noch nicht gesendetes
    /// Bild - roh gehalten für den gRPC-Versand, plus Vorschau-Bitmap und
    /// Dateiname für den Anhang-Chip über der Eingabezeile.</summary>
    private byte[]? _pendingAttachmentBytes;
    private string? _pendingAttachmentMimeType;

    [ObservableProperty]
    private ImageSource? _pendingAttachmentPreview;

    [ObservableProperty]
    private string? _pendingAttachmentFilename;

    public bool HasPendingAttachment => PendingAttachmentPreview != null;

    /// <summary>Feuert einmalig, sobald die erste erfolgreiche gRPC-Verbindung steht.</summary>
    public event Action? Connected;

    /// <summary>Backend fragt eine MEDIUM/HIGH-Risk-Aktion frei: requestId, permission, target, riskLevel, safetyPhrase.</summary>
    public event Action<string, string, string, string, string>? PermissionRequested;

    public MainViewModel()
    {
        _settings = SettingsStore.Load();
        _uiState = AppStateStore.Load();
        LoadWorkspaces();
        LoadChatSessions();
        _grpcClient = new GrpcClientService();
        RestoreUiState();
        _grpcClient.OnMessageReceived += OnGrpcMessageReceived;
        _grpcClient.OnStatusChanged += OnGrpcStatusChanged;
        _grpcClient.OnVoiceStateChanged += OnGrpcVoiceStateChanged;
        _grpcClient.OnLogReceived += OnGrpcLogReceived;
        _grpcClient.OnTaskUpdate += OnGrpcTaskUpdate;
        _grpcClient.OnThinkingUpdate += OnGrpcThinkingUpdate;
        _grpcClient.OnConnectionStateChanged += OnGrpcConnectionStateChanged;
        _grpcClient.OnPermissionRequested += (requestId, permission, target, riskLevel, safetyPhrase) =>
            PermissionRequested?.Invoke(requestId, permission, target, riskLevel, safetyPhrase);
        _grpcClient.OnContextUsageUpdate += OnGrpcContextUsageUpdate;
        _grpcClient.OnAutonomyModeChanged += OnGrpcAutonomyModeChanged;
        _grpcClient.OnReasoningModeChanged += OnGrpcReasoningModeChanged;
        _grpcClient.OnProviderChanged += OnGrpcProviderChanged;
        _grpcClient.OnHighTierModelChanged += OnGrpcHighTierModelChanged;
        _grpcClient.OnSpeakResponsesChanged += OnGrpcSpeakResponsesChanged;
        _grpcClient.OnContextEfficiencyChanged += OnGrpcContextEfficiencyChanged;
        _grpcClient.OnPoolMessageReceived += OnGrpcPoolMessageReceived;
        _grpcClient.OnPoolTaskCompleted += OnGrpcPoolTaskCompleted;
        _grpcClient.OnVisionStatusChanged += OnGrpcVisionStatusChanged;
        _grpcClient.OnVisionImageReceived += OnGrpcVisionImageReceived;
        _grpcClient.OnSpeechEnvelope += OnGrpcSpeechEnvelope;
        _grpcClient.OnAgentTrace += OnGrpcAgentTrace;
        _grpcClient.OnCodingOutput += OnGrpcCodingOutput;
        _grpcClient.OnLanguageChanged += OnGrpcLanguageChanged;
        _ = ConnectAsync();
    }

    /// <summary>Block 7, Phase 69: Recording-Opt-out. Gibt bei Deaktivierung
    /// sofort die Kamera-Hardware im Backend frei.</summary>
    public Task SetVisionEnabledAsync(bool enabled)
    {
        VisionEnabledByUser = enabled;
        return _grpcClient.SendVisionEnabledAsync(enabled);
    }

    private void OnGrpcVisionStatusChanged(bool cameraActive, bool visionAvailable)
    {
        VisionCameraActive = cameraActive;
        VisionAvailable = visionAvailable;
    }

    /// <summary>Sendet einen neuen Autonomie-Modus ans Backend. Der lokale
    /// AutonomyMode-Wert wird erst durch das AutonomyModeUpdate-Broadcast vom
    /// Server aktualisiert (Single Source of Truth bleibt das Backend), nicht
    /// optimistisch hier gesetzt.</summary>
    public Task SetAutonomyModeAsync(string mode)
    {
        return _grpcClient.SendAutonomyModeAsync(mode);
    }

    private void OnGrpcAutonomyModeChanged(string mode)
    {
        AutonomyMode = mode;
    }

    /// <summary>Phase C: fordert den "Denk-Modus" an - der angezeigte Zustand
    /// (ReasoningModeEnabled) wird NUR aus dem Server-Echo gesetzt, nie
    /// optimistisch beim Klick (gleiches Muster wie Autonomie-Modus/Vision-
    /// Toggle), damit UI und Backend nie unbemerkt auseinanderlaufen.</summary>
    public Task SetReasoningModeAsync(bool enabled, string effort)
    {
        return _grpcClient.SendReasoningModeAsync(enabled, effort);
    }

    private void OnGrpcReasoningModeChanged(bool enabled, string effort)
    {
        ReasoningModeEnabled = enabled;
        ReasoningEffort = effort;
    }

    /// <summary>Phase D/1-6: fordert einen Provider- (und optional Modell-)
    /// Wechsel an - ActiveProvider/ActiveModel werden erst durch
    /// OnGrpcProviderChanged (Server-Echo) aktualisiert.</summary>
    public async Task SetProviderAsync(string provider, string? model = null)
    {
        _activeSession.Provider = provider;
        _activeSession.Model = model;
        ActiveProvider = provider;
        ActiveModel = model ?? string.Empty;
        if (SelectedChatSession is not null)
        {
            SelectedChatSession.Provider = provider;
            SelectedChatSession.Model = model;
        }
        SaveActiveChat();
        await _grpcClient.SendProviderAsync(provider, model);
    }

    private void OnGrpcProviderChanged(string provider, bool success, string message, string model)
    {
        ActiveProvider = provider;
        ActiveModel = model;
        _activeSession.Provider = provider;
        _activeSession.Model = string.IsNullOrEmpty(model) ? null : model;
        if (SelectedChatSession is not null)
        {
            SelectedChatSession.Provider = provider;
            SelectedChatSession.Model = string.IsNullOrEmpty(model) ? null : model;
        }
        SaveActiveChat();
        ProviderSwitchError = success ? null : message;

        WindowMessageBus.Publish(new ProviderChangedMessage(provider, model));
    }

    /// <summary>Phase 1-6: lädt den kuratierten Modell-Katalog vom Backend
    /// (statische Provider aus tarno.ai.model_catalog + dynamisch abgefragte
    /// lokale Ollama-Modelle). Wird einmal nach dem ersten Verbindungsaufbau
    /// aufgerufen.</summary>
    public async Task LoadModelCatalogAsync()
    {
        var catalog = await _grpcClient.GetModelCatalogAsync();
        if (catalog == null) return;

        ModelCatalog.Clear();
        foreach (var (providerName, list) in catalog.Providers)
        {
            ModelCatalog[providerName] = list.Models.Select(m => new ModelOptionViewModel
            {
                Id = m.Id,
                Label = m.Label,
                RateLimitNote = m.RateLimitNote,
                Capabilities = string.Join(" · ", m.Capabilities),
            }).ToList();
        }

        OnPropertyChanged(nameof(ModelCatalog));

        PoolAgentCatalog.Clear();
        foreach (var (providerName, list) in ModelCatalog)
        {
            foreach (var model in list)
            {
                PoolAgentCatalog.Add(new PoolAgentSelectionItem
                {
                    Provider = providerName,
                    Model = model.Id,
                    Label = $"{providerName} · {model.Label}",
                });
            }
        }
    }

    /// <summary>Manueller "Starkes Modell"-Schalter (Mistral mistral-medium-2508) -
    /// HighTierModelEnabled wird NUR aus dem Server-Echo gesetzt.</summary>
    public Task SetHighTierModelAsync(bool enabled)
    {
        return _grpcClient.SendHighTierModelAsync(enabled);
    }

    private void OnGrpcHighTierModelChanged(bool enabled)
    {
        HighTierModelEnabled = enabled;
    }

    /// <summary>Chat-Umschalter "Vorlesen" - SpeakResponsesEnabled wird NUR
    /// aus dem Server-Echo gesetzt.</summary>
    public Task SetSpeakResponsesAsync(bool enabled)
    {
        return _grpcClient.SendSpeakResponsesAsync(enabled);
    }

    private void OnGrpcSpeakResponsesChanged(bool enabled)
    {
        SpeakResponsesEnabled = enabled;
    }

    /// <summary>Chat-Umschalter "Kontext-Effizienz" (Beta) -
    /// ContextEfficiencyEnabled wird NUR aus dem Server-Echo gesetzt.</summary>
    public Task SetContextEfficiencyAsync(bool enabled)
    {
        return _grpcClient.SendContextEfficiencyAsync(enabled);
    }

    private void OnGrpcContextEfficiencyChanged(bool enabled)
    {
        ContextEfficiencyEnabled = enabled;
    }

    /// <summary>Settings microphone picker (replaces the researched-and-
    /// rejected "Windows 10/11" toggle - see plan). Fire-and-forget hot-swap
    /// request; the actual confirmation/failure status arrives via
    /// OnMicrophoneDeviceChanged.</summary>
    public Task SetMicrophoneDeviceAsync(string device)
    {
        return _grpcClient.SendMicrophoneDeviceAsync(device);
    }

    public Task SetSpeakerDeviceAsync(string device)
    {
        return _grpcClient.SendSpeakerDeviceAsync(device);
    }

    public Task SetLanguageAsync(string language)
    {
        Settings.Language = language;
        SettingsStore.Save(Settings);
        // PrimaryLanguageOverride darf nur vor dem Laden der UI-Ressourcen
        // gesetzt werden; ein spaeteres Setzen wirft
        // InvalidOperationException. Aktualisierung erfolgt beim naechsten
        // App-Start ueber App.xaml.cs.
        try
        {
            ApplicationLanguages.PrimaryLanguageOverride = language == "en" ? "en-US" : "de-DE";
        }
        catch (InvalidOperationException)
        {
            StatusText = language == "en"
                ? "Language saved. Restart TARNO to fully switch the UI."
                : "Sprache gespeichert. Neustart für vollständige UI-Umschaltung erforderlich.";
        }
        return _grpcClient.SendSetLanguageAsync(language);
    }

    private void OnGrpcLanguageChanged(string language, bool success, string message)
    {
        if (success)
        {
            Settings.Language = language;
            try
            {
                ApplicationLanguages.PrimaryLanguageOverride = language == "en" ? "en-US" : "de-DE";
            }
            catch (InvalidOperationException)
            {
            }
            SettingsStore.Save(Settings);
        }
    }

    public Task<MicrophoneDeviceList?> GetMicrophoneDevicesAsync()
    {
        return _grpcClient.GetMicrophoneDevicesAsync();
    }

    public Task<SpeakerDeviceList?> GetSpeakerDevicesAsync()
    {
        return _grpcClient.GetSpeakerDevicesAsync();
    }

    public Task SendPermissionResponseAsync(string requestId, bool approved, bool persistent)
    {
        return _grpcClient.SendPermissionResponseAsync(requestId, approved, persistent);
    }

    public SolidColorBrush StatusDotBrush
    {
        get
        {
            if (StatusText.StartsWith("Reconnect"))
                return new SolidColorBrush(Color.FromArgb(255, 245, 158, 11)); // Warning orange
            if (StatusText == "Verbindung verloren")
                return new SolidColorBrush(Color.FromArgb(255, 255, 68, 68)); // Error red
            return StatusText switch
            {
                "Bereit" or "Verbunden" => new SolidColorBrush(Color.FromArgb(255, 45, 212, 191)),
                "Denkt nach..." => new SolidColorBrush(Color.FromArgb(255, 245, 158, 11)),
                "Spricht..." => new SolidColorBrush(Color.FromArgb(255, 11, 199, 255)),
                "Hört zu..." => new SolidColorBrush(Color.FromArgb(255, 255, 68, 68)),
                "Voice-Fehler" => new SolidColorBrush(Color.FromArgb(255, 255, 68, 68)),
                _ => new SolidColorBrush(Color.FromArgb(255, 136, 144, 164)),
            };
        }
    }

    public void SelectPage(AppPage page)
    {
        SelectedPage = page;
    }

    partial void OnSelectedPageChanged(AppPage value)
    {
        PersistUiState();
    }

    partial void OnSelectedSidebarModeChanged(SidebarMode value)
    {
        PersistUiState();
        FilterChatSessions();
    }

    partial void OnSelectedWorkspaceChanged(TARNO.UI.Models.Workspace? value)
    {
        PersistUiState();
        FilterChatSessions();
    }

    partial void OnCodingActionModeChanged(ActionMode value)
    {
        var mode = value switch
        {
            ActionMode.Plan => "plan",
            ActionMode.Manual => "manual",
            ActionMode.Auto => "ultimate",
            _ => "manual",
        };
        _ = SetAutonomyModeAsync(mode);
    }

    public void SetDispatcher(Microsoft.UI.Dispatching.DispatcherQueue dispatcher)
    {
        _grpcClient.SetDispatcher(dispatcher);
    }

    public async Task SendChatMessageAsync(string text)
    {
        var message = new ChatMessageViewModel { Role = "user", Text = text, Timestamp = DateTimeOffset.Now };
        var attachmentBytes = _pendingAttachmentBytes;
        var attachmentMimeType = _pendingAttachmentMimeType;
        var attachmentFilename = PendingAttachmentFilename;
        if (attachmentBytes != null)
        {
            message.ImageSource = PendingAttachmentPreview;
            message.ImageCaption = attachmentFilename;
        }
        _activeSession.SidebarMode = SelectedSidebarMode.ToString();
        _activeSession.WorkspaceId = SelectedWorkspace?.Id;
        Messages.Add(message);
        SaveActiveChat();
        ClearPendingAttachment();
        IsBusy = true;

        TARNO.Grpc.Workspace? workspace = null;
        if (SelectedWorkspace is not null && SelectedWorkspace.Folders.Count > 0)
        {
            workspace = new TARNO.Grpc.Workspace
            {
                Id = SelectedWorkspace.Id,
                Name = SelectedWorkspace.Name,
            };
            foreach (var folder in SelectedWorkspace.Folders)
            {
                workspace.Folders.Add(new TARNO.Grpc.WorkspaceFolder
                {
                    Id = folder.Id,
                    Name = folder.Name,
                    Path = folder.Path,
                });
            }
            // Keep the legacy root_path populated for older backend compatibility.
            workspace.RootPath = SelectedWorkspace.Folders[0].Path;
            workspace.IncludePatterns.AddRange(SelectedWorkspace.IncludePatterns);
            workspace.ExcludePatterns.AddRange(SelectedWorkspace.ExcludePatterns);
        }

        var chatMode = SelectedSidebarMode.ToString().ToLowerInvariant();
        await _grpcClient.SendChatAsync(text, _activeSession.Id, attachmentBytes, attachmentFilename, attachmentMimeType, workspace, chatMode);
    }

    public async Task SendCodingTaskAsync(string prompt, System.Collections.Generic.IEnumerable<string> filePaths, bool readOnly)
    {
        TARNO.Grpc.Workspace? workspace = null;
        if (SelectedWorkspace is not null && SelectedWorkspace.Folders.Count > 0)
        {
            workspace = new TARNO.Grpc.Workspace
            {
                Id = SelectedWorkspace.Id,
                Name = SelectedWorkspace.Name,
            };
            foreach (var folder in SelectedWorkspace.Folders)
            {
                workspace.Folders.Add(new TARNO.Grpc.WorkspaceFolder
                {
                    Id = folder.Id,
                    Name = folder.Name,
                    Path = folder.Path,
                });
            }
            workspace.RootPath = SelectedWorkspace.Folders[0].Path;
            workspace.IncludePatterns.AddRange(SelectedWorkspace.IncludePatterns);
            workspace.ExcludePatterns.AddRange(SelectedWorkspace.ExcludePatterns);
        }
        await _grpcClient.SendCodingTaskAsync(prompt, workspace!, filePaths, readOnly, _activeSession.Id);
    }

    /// <summary>Startet einen Agent-Pool-Lauf mit den aktuell in
    /// PoolAgentCatalog ausgewählten Agenten (2-4, genau einer als Lead
    /// markiert - siehe PoolConfig-Validierung serverseitig). Leert das
    /// Transkript vom vorherigen Lauf.</summary>
    public async Task StartPoolTaskAsync(string prompt, System.Collections.Generic.IEnumerable<string> filePaths, bool readOnly)
    {
        var selected = PoolAgentCatalog.Where(a => a.IsSelected).ToList();
        if (selected.Count < 2 || selected.Count > 4) return;
        if (!selected.Any(a => a.IsLead))
        {
            selected[0].IsLead = true;
        }

        // Live-bestaetigter Bug: ohne diesen Guard wurde bei fehlendem
        // SelectedWorkspace stillschweigend ein leerer Workspace (Id/Name
        // ohne RootPath/Folders) an den Server geschickt - Worker bekamen
        // dadurch nie echten Dateizugriff und der finale Merge-Schritt
        // stuerzte serverseitig mit IndexError ab (siehe aider_adapter.py
        // _validate_git_roots). Klarer Fehler statt stillem Fehlschlag -
        // fliesst ueber den bestehenden try/catch in
        // ChatSettingsDialog.OnStartPoolTaskClick in InteractionLogger.Error.
        if (SelectedWorkspace is null || SelectedWorkspace.Folders.Count == 0)
        {
            throw new InvalidOperationException(
                "Kein Workspace-Ordner ausgewählt. Bitte zuerst einen Workspace mit Git-Repository auswählen.");
        }

        var workspace = new TARNO.Grpc.Workspace
        {
            Id = SelectedWorkspace.Id,
            Name = SelectedWorkspace.Name,
        };
        foreach (var folder in SelectedWorkspace.Folders)
        {
            workspace.Folders.Add(new TARNO.Grpc.WorkspaceFolder
            {
                Id = folder.Id,
                Name = folder.Name,
                Path = folder.Path,
            });
        }
        workspace.RootPath = SelectedWorkspace.Folders[0].Path;

        PoolTranscript.Clear();
        PoolAgentStatuses.Clear();
        var startedAt = DateTime.UtcNow;
        foreach (var agent in selected)
        {
            PoolAgentStatuses.Add(new PoolAgentStatusDisplay
            {
                AgentSlug = agent.Slug,
                IsLead = agent.IsLead,
                StartedAtUtc = startedAt,
            });
        }
        IsPoolTaskRunning = true;
        var agents = selected.Select(a => (a.Provider, a.Model, a.IsLead));
        await _grpcClient.SendStartPoolTaskAsync(prompt, workspace, filePaths, agents, readOnly, _activeSession.Id);
    }

    /// <summary>Startet einen Agent-Pool-Lauf direkt aus dem normalen Chat
    /// heraus (Agent-Pool-Umschalter im Chat-Header, ChatPage.xaml) - fügt
    /// die Nutzer-Nachricht wie eine normale Chat-Nachricht in Messages ein,
    /// Pool-Ereignisse erscheinen anschließend als Chat-Bubbles in derselben
    /// Liste (siehe OnGrpcPoolMessageReceived/OnGrpcPoolTaskCompleted) - kein
    /// separates Panel/Fenster, kein eigenes Eingabefeld.</summary>
    public async Task StartPoolTaskFromChatAsync(string text)
    {
        Messages.Add(new ChatMessageViewModel { Role = "user", Text = text, Timestamp = DateTimeOffset.Now });
        _activeSession.SidebarMode = SelectedSidebarMode.ToString();
        _activeSession.WorkspaceId = SelectedWorkspace?.Id;
        SaveActiveChat();
        IsBusy = true;
        try
        {
            await StartPoolTaskAsync(text, System.Array.Empty<string>(), readOnly: false);
        }
        catch
        {
            // Lauf ist nie wirklich gestartet (Validierungsfehler, z.B. kein
            // Workspace oder falsche Agentenzahl) - IsBusy sonst haengen
            // geblieben, da OnGrpcPoolTaskCompleted dann nie feuert.
            IsBusy = false;
            Messages.Add(new ChatMessageViewModel
            {
                Role = "assistant",
                Text = "Agent-Pool konnte nicht gestartet werden - bitte in den Einstellungen (👥 Agent-Pool) 2-4 Agenten auswählen und einen Workspace mit Git-Repository festlegen.",
                Timestamp = DateTimeOffset.Now,
            });
            throw;
        }
    }

    private static string PoolKindLabel(string kind) => kind switch
    {
        "assign" => "Zuweisung",
        "report" => "Bericht",
        "question" => "Frage",
        "merge_decision" => "Zusammenführung",
        _ => "Status",
    };

    private void OnGrpcPoolMessageReceived(PoolMessageEventArgs args)
    {
        if (args.ChatId != _activeSession.Id) return;
        var isLead = PoolAgentCatalog.Any(a => a.IsSelected && a.IsLead && a.Slug == args.FromAgent);

        // Direkt in die normale Chat-Nachrichtenliste einspeisen (keine
        // separate Box/kein eigenes Panel) - jede Pool-Nachricht wird eine
        // eigene Chat-Bubble, mit Agentenname/Art als Praefix.
        Messages.Add(new ChatMessageViewModel
        {
            Role = "assistant",
            Text = $"[{args.FromAgent} → {args.ToAgent} · {PoolKindLabel(args.Kind)}]\n{args.Text}",
            Timestamp = DateTimeOffset.Now,
        });

        PoolTranscript.Add(new PoolMessageDisplay
        {
            FromAgent = args.FromAgent,
            ToAgent = args.ToAgent,
            Kind = args.Kind,
            Text = args.Text,
            SubTaskId = args.SubTaskId,
            IsLead = isLead,
        });

        var now = DateTime.UtcNow;
        var status = PoolAgentStatuses.FirstOrDefault(s => s.AgentSlug == args.FromAgent);
        if (status is null)
        {
            status = new PoolAgentStatusDisplay { AgentSlug = args.FromAgent, IsLead = isLead, StartedAtUtc = now };
            PoolAgentStatuses.Add(status);
        }
        status.RecordActivity(now);
        if (args.Kind == "merge_decision")
        {
            status.IsRunning = false;
        }
    }

    private void OnGrpcPoolTaskCompleted(bool success, string summary, string error, string chatId)
    {
        if (chatId != _activeSession.Id) return;
        IsPoolTaskRunning = false;
        IsBusy = false;
        var now = DateTime.UtcNow;
        foreach (var status in PoolAgentStatuses)
        {
            status.IsRunning = false;
            status.UpdateElapsed(now);
        }
        Messages.Add(new ChatMessageViewModel
        {
            Role = "assistant",
            Text = success ? summary : $"Agent-Pool-Lauf fehlgeschlagen: {error}",
            Timestamp = DateTimeOffset.Now,
        });
        SaveActiveChat();
        PoolTranscript.Add(new PoolMessageDisplay
        {
            FromAgent = "pool",
            ToAgent = "broadcast",
            Kind = "status",
            Text = success ? summary : $"Fehlgeschlagen: {error}",
        });
    }

    /// <summary>Übernimmt ein vom Datei-Picker gewähltes Bild als Anhang für
    /// die nächste gesendete Chat-Nachricht - baut sofort eine Vorschau-
    /// Bitmap für den Anhang-Chip über der Eingabezeile.</summary>
    public async Task SetPendingAttachmentAsync(byte[] bytes, string filename, string mimeType)
    {
        _pendingAttachmentBytes = bytes;
        _pendingAttachmentMimeType = mimeType;
        PendingAttachmentFilename = filename;

        var bitmap = new BitmapImage();
        using (var stream = new InMemoryRandomAccessStream())
        {
            await stream.WriteAsync(bytes.AsBuffer());
            stream.Seek(0);
            await bitmap.SetSourceAsync(stream);
        }
        PendingAttachmentPreview = bitmap;
        OnPropertyChanged(nameof(HasPendingAttachment));
    }

    public void ClearPendingAttachment()
    {
        _pendingAttachmentBytes = null;
        _pendingAttachmentMimeType = null;
        PendingAttachmentFilename = null;
        PendingAttachmentPreview = null;
        OnPropertyChanged(nameof(HasPendingAttachment));
    }

    /// <summary>Stops the current in-flight chat request. The backend can't abort
    /// the blocking LLM HTTP call already in progress, but discards the eventual
    /// response instead of showing it late - and the UI resets immediately.</summary>
    public async Task CancelCurrentChatAsync()
    {
        IsBusy = false;
        await _grpcClient.SendCancelChatAsync();
    }

    /// <summary>Toggles voice listening on/off based on current VoiceState.</summary>
    public async Task ToggleVoiceAsync()
    {
        await ToggleVoiceAsync(VoiceState == "VOICE_IDLE");
    }

    public async Task ToggleVoiceAsync(bool active)
    {
        if (active)
        {
            try
            {
                var audioManager = new AudioInputManager();
                // Validiert das Mikrofon lokal (WASAPI-Check + Fallback), bevor der gRPC-Befehl gesendet wird.
                // Das verhindert, dass das Backend in einen ungültigen Zustand gerät.
                using var testMic = audioManager.GetBestMicrophone(Settings.MicrophoneDevice);
                // Wenn wir hier ankommen, ist mindestens ein Mikrofon bereit.
            }
            catch (Exception ex)
            {
                StatusText = "Voice-Fehler";
                OnPropertyChanged(nameof(StatusDotBrush));
                VoiceState = "VOICE_ERROR";
                Logs.Add(new LogEntryViewModel
                {
                    Level = "ERROR",
                    Module = "AudioInputManager",
                    Message = $"Mikrofon-Initialisierung fehlgeschlagen: {ex.Message}",
                    Timestamp = DateTimeOffset.Now,
                    FormattedTimestamp = DateTimeOffset.Now.ToString("HH:mm:ss.fff"),
                });
                return;
            }
        }
        await _grpcClient.SendVoiceCommandAsync(active);
    }

    /// <summary>Phase B: einmaliges Diktat fürs Chat-Textfeld - blockiert bis
    /// zu ~45s auf eine gesprochene Äußerung, KEIN Wake-Word-/Voice-Loop.</summary>
    public Task<(bool Success, string Text, string Error)> DictateAsync(string eagerness)
    {
        return _grpcClient.DictateAsync(eagerness);
    }

    public async Task<(bool Success, string Message)> SetApiKeyAsync(string provider, string apiKey)
    {
        return await _grpcClient.SetApiKeyAsync(provider, apiKey);
    }

    public async Task<System.Collections.Generic.Dictionary<string, bool>> GetApiKeyStatusAsync()
    {
        return await _grpcClient.GetApiKeyStatusAsync();
    }

    /// <summary>Lädt Fakten/Episoden aus dem Gedächtnis-Layer (Block 4) für
    /// die MemoryPage. Leerer 'search' liefert alles (bis zum Server-Limit).</summary>
    public async Task LoadMemoryAsync(string search = "")
    {
        var summary = await _grpcClient.GetMemorySummaryAsync(search);
        MemoryEnabled = summary?.MemoryEnabled ?? false;

        MemoryFacts.Clear();
        MemoryEpisodes.Clear();
        if (summary is null)
        {
            return;
        }

        foreach (var fact in summary.Facts)
        {
            MemoryFacts.Add(new MemoryFactViewModel
            {
                Key = fact.Key,
                Value = fact.Value,
                Source = fact.Source,
                UpdatedAt = DateTimeOffset.FromUnixTimeMilliseconds(fact.UpdatedAt).LocalDateTime,
            });
        }
        foreach (var episode in summary.Episodes)
        {
            MemoryEpisodes.Add(new MemoryEpisodeViewModel
            {
                Summary = episode.Summary,
                Tags = string.Join(", ", episode.Tags),
                CreatedAt = DateTimeOffset.FromUnixTimeMilliseconds(episode.CreatedAt).LocalDateTime,
            });
        }
    }

    public async Task<(bool Success, int Count, string Message)> ImportMemoryAsync(string jsonText)
    {
        var result = await _grpcClient.ImportMemoryAsync(jsonText);
        if (result.Success)
        {
            await LoadMemoryAsync();
        }
        return result;
    }

    private async Task ConnectAsync()
    {
        try
        {
            ConnectionStatus = "Verbinde...";
            await _grpcClient.ConnectAsync("localhost", 50051);
        }
        catch (Exception ex)
        {
            ConnectionStatus = FormatConnectionError(ex);
        }
    }

    /// <summary>KERNFIX (Clipping-Bug): eine rohe Grpc.Core.RpcException.Message
    /// (mehrzeiliger StatusCode+Detail-Dump, oft mehrere hundert Zeichen) landete
    /// vorher unveraendert in ConnectionStatus - bei FontSize 26 auf HomePage bzw.
    /// im schmalen Sidebar-Footer wurde das durch WinUI3s Border+CornerRadius-Clip
    /// hart abgeschnitten, ohne Ellipse, ohne dass der Rest sichtbar/erreichbar war.
    /// Jetzt: kurzer, verstaendlicher deutscher Text je StatusCode; die volle
    /// Exception bleibt weiterhin im Log (ueber die aufrufende Stelle bzw. spaeteres
    /// Logging), nur die UI-Anzeige wird begrenzt.</summary>
    private static string FormatConnectionError(Exception ex)
    {
        if (ex is RpcException rpc)
        {
            return rpc.StatusCode switch
            {
                StatusCode.Unavailable => "Backend offline",
                StatusCode.DeadlineExceeded => "Zeitüberschreitung",
                StatusCode.Unauthenticated or StatusCode.PermissionDenied => "Kein Zugriff",
                StatusCode.Internal => "Backend-Fehler",
                _ => $"Fehler ({rpc.StatusCode})",
            };
        }

        var firstLine = ex.Message.Split('\n', 2)[0];
        const int maxLength = 40;
        return "Fehler: " + (firstLine.Length > maxLength ? firstLine[..maxLength] + "…" : firstLine);
    }

    private async void OnGrpcConnectionStateChanged(bool connected)
    {
        ConnectionStatus = connected ? "Online" : "Offline";
        if (connected)
        {
            StatusText = "Verbunden";
            OnPropertyChanged(nameof(StatusDotBrush));
            try
            {
                SystemInfo = await _grpcClient.GetSystemInfoAsync();
            }
            catch (Exception)
            {
                SystemInfo = "—";
            }

            if (!_hasConnectedOnce)
            {
                _hasConnectedOnce = true;
                _ = LoadModelCatalogAsync();
                Connected?.Invoke();
            }
        }
        else
        {
            StatusText = "Verbindung verloren";
            OnPropertyChanged(nameof(StatusDotBrush));
        }
    }

    private void OnGrpcMessageReceived(string role, string text, string chatId, string turnId)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        var targetChatId = string.IsNullOrEmpty(chatId) ? _activeSession.Id : chatId;
        var isActive = targetChatId == _activeSession.Id;

        if (isActive)
        {
            // User-Nachrichten werden bereits lokal in SendChatMessageAsync angezeigt;
            // der Server broadcastet sie zusätzlich (für Voice-Eingaben). Text-Echos
            // der eigenen Eingabe würden sonst doppelt erscheinen.
            if (role == "user" && Messages.Count > 0
                && Messages[^1].Role == "user" && Messages[^1].Text == text)
            {
                return;
            }

            if (role == "assistant" && !string.IsNullOrEmpty(turnId))
            {
                var existing = Messages.LastOrDefault(m => m.Role == "assistant" && m.TurnId == turnId);
                if (existing != null)
                {
                    existing.Text = text;
                    IsBusy = false;
                    ThinkingState.IsActive = false;
                    if (_pendingVisionImageSource != null)
                    {
                        existing.ImageSource = _pendingVisionImageSource;
                        existing.ImageCaption = _pendingVisionCaption;
                        _pendingVisionImageSource = null;
                        _pendingVisionCaption = null;
                    }
                    SaveActiveChat();
                    return;
                }
            }

            var msg = new ChatMessageViewModel { Role = role, Text = text, ChatId = targetChatId, TurnId = turnId, Timestamp = DateTimeOffset.Now };
            Messages.Add(msg);

            WindowMessageBus.Publish(new ChatMessageReceivedMessage(targetChatId, role, text));

            if (role == "assistant")
            {
                IsBusy = false;
                ThinkingState.IsActive = false;
                if (_pendingVisionImageSource != null)
                {
                    msg.ImageSource = _pendingVisionImageSource;
                    msg.ImageCaption = _pendingVisionCaption;
                    _pendingVisionImageSource = null;
                    _pendingVisionCaption = null;
                }
            }
            SaveActiveChat();
        }
        else
        {
            var sessions = ChatStore.Load();
            var session = sessions.FirstOrDefault(s => s.Id == targetChatId);
            if (session == null)
            {
                return;
            }
            session.Messages.Add(new ChatMessageData
            {
                Role = role,
                Text = text,
                Timestamp = DateTimeOffset.Now,
            });
            session.UpdatedAt = DateTimeOffset.Now;
            ChatStore.SaveSession(session);
            var vm = ChatSessions.FirstOrDefault(s => s.Id == targetChatId);
            if (vm is not null)
            {
                vm.UpdatedAt = session.UpdatedAt;
                vm.MessageCount = session.Messages.Count;
            }
        }
    }

    private void OnGrpcContextUsageUpdate(int used, int max)
    {
        ContextUsedTokens = used;
        ContextMaxTokens = max;
        OnPropertyChanged(nameof(ContextUsagePercent));
    }

    private void OnGrpcStatusChanged(string status)
    {
        StatusText = status;
        OnPropertyChanged(nameof(StatusDotBrush));
    }

    private void OnGrpcVoiceStateChanged(string state)
    {
        VoiceState = state;
        IsVoiceMuted = state == "VOICE_IDLE" || state == "VOICE_ERROR";
    }

    private void OnGrpcLogReceived(string level, string message, string module, long timestampMs)
    {
        var timestamp = DateTimeOffset.FromUnixTimeMilliseconds(timestampMs).ToLocalTime();
        Logs.Add(new LogEntryViewModel
        {
            Level = level,
            Message = message,
            Module = module,
            Timestamp = timestamp,
            FormattedTimestamp = timestamp.ToString("HH:mm:ss.fff"),
        });
        if (Logs.Count > 500)
        {
            Logs.RemoveAt(0);
        }
        // Nicht automatisch zur Logs-Seite wechseln: bei dauerhaft fehlerhaften
        // Pipelines würde der Nutzer sonst dort gefangen sein. Logs bleiben
        // jederzeit über den Nav-Button erreichbar.
    }

    private void OnGrpcTaskUpdate(string id, string title, int progress)
    {
        var existing = FindTask(id);
        if (existing is not null)
        {
            existing.Title = title;
            existing.Progress = progress;
        }
        else
        {
            Tasks.Add(new TaskViewModel
            {
                Id = id,
                Title = title,
                Progress = progress,
                Status = "running"
            });
        }
    }

    private TaskViewModel? FindTask(string id)
    {
        foreach (var task in Tasks)
        {
            if (task.Id == id)
            {
                return task;
            }
        }
        return null;
    }

    private void OnGrpcThinkingUpdate(bool active, string stage, string reasoning, string stageKey)
    {
        ThinkingState.IsActive = active;
        ThinkingState.Message = stage;
        ThinkingState.Reasoning = reasoning;
        ThinkingState.StageKey = stageKey;
        if (active)
        {
            ThinkingState.StartedAt = DateTimeOffset.Now;
        }
    }

    private void OnGrpcVisionImageReceived(byte[] jpegBytes, string caption)
    {
        var stream = new InMemoryRandomAccessStream();
        using (var writer = new DataWriter(stream))
        {
            writer.WriteBytes(jpegBytes);
            writer.StoreAsync().AsTask().Wait();
            writer.DetachStream();
        }
        stream.Seek(0);
        var bitmap = new BitmapImage();
        bitmap.SetSource(stream);

        var lastAssistant = Messages.LastOrDefault(m => m.Role == "assistant");
        if (lastAssistant != null)
        {
            lastAssistant.ImageSource = bitmap;
            lastAssistant.ImageCaption = caption;
            _pendingVisionImageSource = null;
            _pendingVisionCaption = null;
        }
        else
        {
            // Bild ist schneller als die Text-Antwort: puffern, bis die
            // zugehörige Assistant-Nachricht in OnGrpcMessageReceived ankommt.
            _pendingVisionImageSource = bitmap;
            _pendingVisionCaption = caption;
        }
    }

    private void OnGrpcCodingOutput(string kind, string text, string chatId)
    {
        CodingOutputs.Add($"[{kind}] {text}");
    }

    private void LoadWorkspaces()
    {
        try
        {
            var persisted = WorkspaceStore.Load();
            Workspaces.Clear();
            foreach (var workspace in persisted)
            {
                Workspaces.Add(workspace);
            }
            SelectedWorkspace = Workspaces.FirstOrDefault();
        }
        catch
        {
            // Workspaces sind best-effort; bei Fehler einfach leer starten.
        }
    }

    private void LoadChatSessions()
    {
        try
        {
            var sessions = ChatStore.Load();
            ChatSessions.Clear();
            foreach (var session in sessions)
            {
                ChatSessions.Add(ToViewModel(session));
            }
            if (ChatSessions.Count == 0)
            {
                _activeSession = new ChatSession { Title = "Neuer Chat" };
                ChatSessions.Add(ToViewModel(_activeSession));
            }
            FilterChatSessions();
        }
        catch
        {
            _activeSession = new ChatSession { Title = "Neuer Chat" };
            ChatSessions.Add(ToViewModel(_activeSession));
            FilterChatSessions();
        }
    }

    private static ChatSessionViewModel ToViewModel(ChatSession session)
    {
        return new ChatSessionViewModel
        {
            Id = session.Id,
            Title = session.Title,
            UpdatedAt = session.UpdatedAt,
            MessageCount = session.Messages?.Count ?? 0,
            WorkspaceId = session.WorkspaceId,
            SidebarMode = session.SidebarMode,
            Provider = session.Provider,
            Model = session.Model,
        };
    }

    private void FilterChatSessions()
    {
        FilteredChatSessions.Clear();
        var selectedMode = SelectedSidebarMode.ToString();
        var selectedWorkspaceId = SelectedWorkspace?.Id;
        foreach (var session in ChatSessions)
        {
            if (session.SidebarMode == selectedMode)
            {
                if (SelectedSidebarMode == SidebarMode.Code && !string.IsNullOrEmpty(selectedWorkspaceId))
                {
                    if (session.WorkspaceId == selectedWorkspaceId)
                    {
                        FilteredChatSessions.Add(session);
                    }
                }
                else
                {
                    FilteredChatSessions.Add(session);
                }
            }
        }
    }

    private void RestoreUiState()
    {
        if (Enum.TryParse<AppPage>(_uiState.SelectedPage, true, out var page))
        {
            SelectedPage = page;
        }
        if (Enum.TryParse<SidebarMode>(_uiState.SidebarMode, true, out var mode))
        {
            SelectedSidebarMode = mode;
        }
        if (!string.IsNullOrEmpty(_uiState.ActiveWorkspaceId))
        {
            SelectedWorkspace = Workspaces.FirstOrDefault(w => w.Id == _uiState.ActiveWorkspaceId);
        }
        var active = ChatSessions.FirstOrDefault(s => s.Id == _uiState.ActiveChatId)
                     ?? ChatSessions.FirstOrDefault();
        if (active is not null)
        {
            LoadChatSession(active.Id);
        }
    }

    private void PersistUiState()
    {
        _uiState.SelectedPage = SelectedPage.ToString();
        _uiState.SidebarMode = SelectedSidebarMode.ToString();
        _uiState.ActiveChatId = _activeSession.Id;
        _uiState.ActiveWorkspaceId = SelectedWorkspace?.Id;
        AppStateStore.Save(_uiState);
    }

    public void NewChat()
    {
        SaveActiveChat();
        _activeSession = new ChatSession
        {
            Title = "Neuer Chat",
            SidebarMode = SelectedSidebarMode.ToString(),
        };
        ChatSessions.Insert(0, ToViewModel(_activeSession));
        FilterChatSessions();
        SelectedChatSession = FilteredChatSessions.FirstOrDefault();
        ActiveProvider = "mistral";
        ActiveModel = string.Empty;
        Messages.Clear();
        TraceItems.Clear();
        SaveActiveChat();
        _ = _grpcClient.SendActiveChatAsync(_activeSession.Id);
        PersistUiState();
    }

    public void NewChatForWorkspace(string workspaceId)
    {
        SaveActiveChat();
        _activeSession = new ChatSession
        {
            Title = "Neuer Workspace-Chat",
            WorkspaceId = workspaceId,
            SidebarMode = SelectedSidebarMode.ToString(),
        };
        var vm = ToViewModel(_activeSession);
        ChatSessions.Insert(0, vm);
        FilterChatSessions();
        SelectedChatSession = FilteredChatSessions.FirstOrDefault(s => s.Id == vm.Id);
        ActiveProvider = "mistral";
        ActiveModel = string.Empty;
        Messages.Clear();
        TraceItems.Clear();
        SaveActiveChat();
        _ = _grpcClient.SendActiveChatAsync(_activeSession.Id);
        PersistUiState();
    }

    public void SelectChatSession(string id)
    {
        if (_isSelectingChat)
        {
            return;
        }
        _isSelectingChat = true;
        try
        {
            SaveActiveChat();
            LoadChatSession(id);
            PersistUiState();
        }
        finally
        {
            _isSelectingChat = false;
        }
    }

    public void DeleteChatSession(string id)
    {
        var vm = ChatSessions.FirstOrDefault(s => s.Id == id);
        if (vm is null)
        {
            return;
        }
        ChatSessions.Remove(vm);
        FilteredChatSessions.Remove(vm);
        ChatStore.Delete(id);
        if (_activeSession.Id == id)
        {
            var next = FilteredChatSessions.FirstOrDefault() ?? ChatSessions.FirstOrDefault();
            LoadChatSession(next?.Id);
        }
        PersistUiState();
    }

    private void LoadChatSession(string? id)
    {
        if (string.IsNullOrEmpty(id))
        {
            _activeSession = new ChatSession { Title = "Neuer Chat" };
            ActiveProvider = "mistral";
            ActiveModel = string.Empty;
            Messages.Clear();
            TraceItems.Clear();
            SelectedChatSession = null;
            _ = _grpcClient.SendActiveChatAsync(_activeSession.Id);
            return;
        }

        try
        {
            var all = ChatStore.Load();
            var session = all.FirstOrDefault(s => s.Id == id) ?? new ChatSession { Title = "Neuer Chat" };
            session.Messages ??= new List<ChatMessageData>();
            _activeSession = session;
            Messages.Clear();
            TraceItems.Clear();
            foreach (var msg in session.Messages)
            {
                Messages.Add(new ChatMessageViewModel
                {
                    Role = msg.Role,
                    Text = msg.Text,
                    Timestamp = msg.Timestamp,
                    ImageCaption = msg.ImageCaption,
                });
            }
            SelectedChatSession = ChatSessions.FirstOrDefault(s => s.Id == id);

            var previousProvider = ActiveProvider;
            var previousModel = ActiveModel;
            ActiveProvider = string.IsNullOrEmpty(session.Provider) ? "mistral" : session.Provider;
            ActiveModel = session.Model ?? string.Empty;
            if (SelectedChatSession is not null)
            {
                SelectedChatSession.Provider = session.Provider;
                SelectedChatSession.Model = session.Model;
            }
            if (!string.IsNullOrEmpty(session.Provider) &&
                (session.Provider != previousProvider || session.Model != previousModel))
            {
                _ = _grpcClient.SendProviderAsync(session.Provider, session.Model);
            }
            if (!string.IsNullOrEmpty(_activeSession.Id))
            {
                _ = _grpcClient.SendActiveChatAsync(_activeSession.Id);
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("MAIN", $"LoadChatSession failed for id '{id}': {ex}");
            _activeSession = new ChatSession { Title = "Neuer Chat" };
            ActiveProvider = "mistral";
            ActiveModel = string.Empty;
            Messages.Clear();
            TraceItems.Clear();
            SelectedChatSession = null;
            if (!string.IsNullOrEmpty(_activeSession.Id))
            {
                _ = _grpcClient.SendActiveChatAsync(_activeSession.Id);
            }
        }
    }

    public void SaveActiveChat()
    {
        try
        {
            _activeSession.Messages = Messages.Select(m => new ChatMessageData
            {
                Role = m.Role,
                Text = m.Text,
                Timestamp = m.Timestamp,
                ImageCaption = m.ImageCaption,
            }).ToList();
            _activeSession.Title = Messages.FirstOrDefault(m => m.Role == "user")?.Text?.Trim() ?? "Neuer Chat";
            if (_activeSession.Title.Length > 40)
            {
                _activeSession.Title = _activeSession.Title[..40] + "…";
            }
            _activeSession.UpdatedAt = DateTimeOffset.Now;
            ChatStore.SaveSession(_activeSession);
            var vm = ChatSessions.FirstOrDefault(s => s.Id == _activeSession.Id);
            if (vm is not null)
            {
                vm.Title = _activeSession.Title;
                vm.UpdatedAt = _activeSession.UpdatedAt;
                vm.MessageCount = _activeSession.Messages.Count;
                vm.SidebarMode = _activeSession.SidebarMode;
                vm.WorkspaceId = _activeSession.WorkspaceId;
            }
        }
        catch
        {
            // Best-effort.
        }
    }

    /// <summary>Echte Amplituden-Huellkurve + Dauer der startenden TTS-Wiedergabe -
    /// treibt die Orb-Ganzkoerper-Resonanz in ChatPage/VoicePage an, statt
    /// eines rein prozeduralen Loops.</summary>
    public event Action<float[], double>? SpeechEnvelopeReceived;

    private void OnGrpcSpeechEnvelope(float[] levels, double durationSeconds)
    {
        SpeechEnvelopeReceived?.Invoke(levels, durationSeconds);
    }

    private void OnGrpcAgentTrace(TARNO.Grpc.AgentTrace trace)
    {
        if (!string.IsNullOrEmpty(trace.ChatId) && trace.ChatId != _activeSession.Id)
        {
            return;
        }
        if (trace.DetailCase == TARNO.Grpc.AgentTrace.DetailOneofCase.ThoughtDelta)
        {
            var delta = trace.ThoughtDelta;
            var existing = FindTraceItem(trace.TraceId);
            if (existing is not null)
            {
                existing.Content += delta.Delta;
                if (!string.IsNullOrEmpty(delta.Title))
                {
                    existing.Title = delta.Title;
                }
                existing.IsFinished = delta.Finished;
                existing.IsCollapsed = delta.Collapsed;
            }
            else
            {
                TraceItems.Add(new AgentTraceViewModel
                {
                    TraceId = trace.TraceId,
                    ParentId = trace.ParentId,
                    TurnId = trace.TurnId,
                    Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(trace.Timestamp).DateTime,
                    TraceType = "thought_delta",
                    Title = delta.Title,
                    Content = delta.Delta,
                    IsFinished = delta.Finished,
                    IsCollapsed = delta.Collapsed,
                });
            }

            bool isResponseStart = delta.Title == "Antwort wird generiert...";
            bool isResponseContinuation = _streamingResponseTraceId == trace.TraceId;
            if (isResponseStart)
            {
                _streamingResponseTraceId = trace.TraceId;
                isResponseContinuation = true;
            }
            if (isResponseContinuation && !string.IsNullOrEmpty(trace.TurnId))
            {
                var assistant = Messages.LastOrDefault(m => m.Role == "assistant" && m.TurnId == trace.TurnId);
                if (assistant == null)
                {
                    assistant = new ChatMessageViewModel
                    {
                        Role = "assistant",
                        ChatId = trace.ChatId,
                        TurnId = trace.TurnId,
                        Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(trace.Timestamp).DateTime,
                    };
                    Messages.Add(assistant);
                }
                assistant.Text += delta.Delta;
                IsBusy = true;
            }
        }
        else if (trace.DetailCase == TARNO.Grpc.AgentTrace.DetailOneofCase.ToolStart)
        {
            var start = trace.ToolStart;
            TraceItems.Add(new AgentTraceViewModel
            {
                TraceId = trace.TraceId,
                ParentId = trace.ParentId,
                TurnId = trace.TurnId,
                Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(trace.Timestamp).DateTime,
                TraceType = "tool_start",
                Target = start.Target,
                Description = start.Description,
                IsCollapsed = false,
            });
        }
        else if (trace.DetailCase == TARNO.Grpc.AgentTrace.DetailOneofCase.ToolEnd)
        {
            var end = trace.ToolEnd;
            TraceItems.Add(new AgentTraceViewModel
            {
                TraceId = trace.TraceId,
                ParentId = trace.ParentId,
                TurnId = trace.TurnId,
                Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(trace.Timestamp).DateTime,
                TraceType = "tool_end",
                Target = end.Target,
                Success = end.Success,
                ResultSummary = end.ResultSummary,
                IsCollapsed = false,
            });
        }
        else if (trace.DetailCase == TARNO.Grpc.AgentTrace.DetailOneofCase.FileDiff)
        {
            var diff = trace.FileDiff;
            TraceItems.Add(new AgentTraceViewModel
            {
                TraceId = trace.TraceId,
                ParentId = trace.ParentId,
                TurnId = trace.TurnId,
                Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(trace.Timestamp).DateTime,
                TraceType = "file_diff",
                Target = diff.Path,
                IsNewFile = diff.IsNew,
                Language = diff.Language,
                Content = diff.Content,
                IsCollapsed = false,
            });
        }
    }

    private AgentTraceViewModel? FindTraceItem(string traceId)
    {
        foreach (var item in TraceItems)
        {
            if (item.TraceId == traceId)
            {
                return item;
            }
        }
        return null;
    }
}

public partial class ChatMessageViewModel : ObservableObject
{
    [ObservableProperty]
    private string _role = "user";

    [ObservableProperty]
    private string _text = string.Empty;

    [ObservableProperty]
    private string _turnId = string.Empty;

    [ObservableProperty]
    private string _chatId = string.Empty;

    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.Now;

    [ObservableProperty]
    private ImageSource? _imageSource;

    [ObservableProperty]
    private string? _imageCaption;
}

public class LogEntryViewModel
{
    public string Level { get; set; } = "INFO";
    public string Message { get; set; } = string.Empty;
    public string Module { get; set; } = string.Empty;
    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.Now;
    public string FormattedTimestamp { get; set; } = DateTimeOffset.Now.ToString("HH:mm:ss.fff");
}

public class MemoryFactViewModel
{
    public string Key { get; set; } = string.Empty;
    public string Value { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty;
    public DateTime UpdatedAt { get; set; }
}

public class MemoryEpisodeViewModel
{
    public string Summary { get; set; } = string.Empty;
    public string Tags { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }
}
