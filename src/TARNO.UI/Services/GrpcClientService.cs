using Grpc.Core;
using Grpc.Net.Client;
using TARNO.Grpc;
using Microsoft.UI.Dispatching;
using System;
using System.Threading;
using System.Threading.Tasks;

namespace TARNO.UI.Services;

/// <summary>Ein Inter-Agent-Kommunikationsereignis aus einem laufenden
/// Agent-Pool-Lauf (siehe tarno/ai/pool/models.py PoolMessage).</summary>
public sealed record PoolMessageEventArgs(
    string FromAgent,
    string ToAgent,
    string Kind,
    string Text,
    long TimestampMs,
    string ChatId,
    string SubTaskId);

/// <summary>
/// C# gRPC client that connects to the TARNO Python backend.
/// Generated types come from tarno/grpc/tarno.proto via Grpc.Tools.
///
/// Phase 2 additions:
/// - Auto-reconnect with exponential backoff on connection loss.
/// - OnConnectionStateChanged event for UI feedback.
/// - Resilient send methods that tolerate temporary disconnects.
/// </summary>
public sealed class GrpcClientService : IDisposable
{
    private GrpcChannel? _channel;
    private Tarno.TarnoClient? _client;
    private AsyncDuplexStreamingCall<ClientMessage, ServerMessage>? _stream;
    private CancellationTokenSource? _cts;
    private DispatcherQueue? _dispatcher;

    private string _host = "localhost";
    private int _port = 50051;
    private bool _isConnected;
    private int _reconnectAttempts;

    private const int MaxReconnectDelayMs = 30_000;
    private const int BaseReconnectDelayMs = 1_000;

    public event Action<string, string, string, string>? OnMessageReceived; // role, text, chatId, turnId
    public event Action<string>? OnStatusChanged;
    public event Action<string>? OnVoiceStateChanged;
    public event Action<string, string, string, long>? OnLogReceived;
    public event Action<string, string, int>? OnTaskUpdate;
    public event Action<bool, string, string, string>? OnThinkingUpdate;
    public event Action<bool>? OnConnectionStateChanged;
    public event Action<string, string, string, string, string>? OnPermissionRequested; // requestId, permission, target, riskLevel, safetyPhrase
    public event Action<int, int>? OnContextUsageUpdate; // used, max tokens
    public event Action<string>? OnAutonomyModeChanged; // "manual" | "balanced" | "plan" | "ultimate"
    public event Action<bool, bool>? OnVisionStatusChanged; // cameraActive, visionAvailable
    public event Action<bool, string>? OnReasoningModeChanged; // enabled, effort
    public event Action<string, bool, string, string>? OnProviderChanged; // provider, success, message, model
    public event Action<bool>? OnHighTierModelChanged; // enabled
    public event Action<bool>? OnSpeakResponsesChanged; // enabled
    public event Action<bool>? OnContextEfficiencyChanged; // enabled
    public event Action<PoolMessageEventArgs>? OnPoolMessageReceived;
    public event Action<bool, string, string, string>? OnPoolTaskCompleted; // success, summary, error, chatId
    public event Action<byte[], string>? OnVisionImageReceived; // jpegBytes, caption
    public event Action<float[], double>? OnSpeechEnvelope; // Amplituden-Huellkurve + echte Dauer der startenden TTS-Wiedergabe
    public event Action<string, bool, string>? OnMicrophoneDeviceChanged; // activeDevice, loading, status
    public event Action<string, bool, string>? OnSpeakerDeviceChanged; // activeDevice, loading, status
    public event Action<string, bool, string>? OnLanguageChanged; // language, success, message
    public event Action<AgentTrace>? OnAgentTrace; // live thought/tool/diff stream
    public event Action<string, string, string>? OnCodingOutput; // kind, text, chatId

    public bool IsConnected => _isConnected;

    public void SetDispatcher(DispatcherQueue dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public async Task ConnectAsync(string host, int port)
    {
        _host = host;
        _port = port;
        _cts = new CancellationTokenSource();
        await ConnectInternalAsync(_cts.Token);
    }

    private async Task ConnectInternalAsync(CancellationToken ct)
    {
        var address = $"http://{_host}:{_port}";

        _stream?.Dispose();
        _channel?.Dispose();

        _channel = GrpcChannel.ForAddress(address, new GrpcChannelOptions
        {
            // 16MB statt 8MB - Bild-Uploads (Phase A) koennen die alte
            // Grenze ueberschreiten; muss zum Server-seitigen Limit passen.
            MaxReceiveMessageSize = 16 * 1024 * 1024,
            MaxSendMessageSize = 16 * 1024 * 1024,
        });
        _client = new Tarno.TarnoClient(_channel);
        _stream = _client.Stream();

        SetConnected(true);
        _reconnectAttempts = 0;

        await ReadLoopWithReconnectAsync(ct);
    }

    public async Task SendChatAsync(string text, string chatId, byte[]? attachmentData = null, string? attachmentFilename = null, string? attachmentMimeType = null, TARNO.Grpc.Workspace? workspace = null, string chatMode = "chat")
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            var chatInput = new ChatInput { Text = text, ChatId = chatId, ChatMode = chatMode };
            if (attachmentData is { Length: > 0 })
            {
                chatInput.AttachmentData = Google.Protobuf.ByteString.CopyFrom(attachmentData);
                chatInput.AttachmentFilename = attachmentFilename ?? string.Empty;
                chatInput.AttachmentMimeType = attachmentMimeType ?? string.Empty;
            }
            if (workspace != null)
            {
                chatInput.Workspace = workspace;
            }
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                ChatInput = chatInput
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendCodingTaskAsync(string prompt, TARNO.Grpc.Workspace workspace, System.Collections.Generic.IEnumerable<string> filePaths, bool readOnly, string chatId)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            var request = new CodingTaskRequest
            {
                Prompt = prompt,
                Workspace = workspace,
                ReadOnly = readOnly,
                ChatId = chatId,
            };
            foreach (var path in filePaths)
            {
                request.FilePaths.Add(path);
            }
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                CodingTask = request
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendStartPoolTaskAsync(
        string prompt,
        TARNO.Grpc.Workspace workspace,
        System.Collections.Generic.IEnumerable<string> filePaths,
        System.Collections.Generic.IEnumerable<(string Provider, string Model, bool IsLead)> agents,
        bool readOnly,
        string chatId)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            var request = new StartPoolTaskRequest
            {
                Prompt = prompt,
                Workspace = workspace,
                ReadOnly = readOnly,
                ChatId = chatId,
            };
            foreach (var path in filePaths)
            {
                request.FilePaths.Add(path);
            }
            foreach (var agent in agents)
            {
                request.Agents.Add(new PoolAgentSpecProto
                {
                    Provider = agent.Provider,
                    Model = agent.Model,
                    IsLead = agent.IsLead,
                });
            }
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                StartPoolTask = request
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendVoiceCommandAsync(bool active)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                VoiceCommand = new VoiceCommand { Active = active }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendAutonomyModeAsync(string mode)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetAutonomyMode = new SetAutonomyMode { Mode = mode }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendVisionEnabledAsync(bool enabled)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetVisionEnabled = new SetVisionEnabled { Enabled = enabled }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendReasoningModeAsync(bool enabled, string effort)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetReasoningMode = new SetReasoningMode { Enabled = enabled, Effort = effort }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendHighTierModelAsync(bool enabled)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetHighTierModel = new SetHighTierModel { Enabled = enabled }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendSpeakResponsesAsync(bool enabled)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetSpeakResponses = new SetSpeakResponses { Enabled = enabled }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendContextEfficiencyAsync(bool enabled)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetContextEfficiency = new SetContextEfficiency { Enabled = enabled }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    // Tells the backend which chat is currently open, so voice-recognized
    // speech (which has no per-request chat_id of its own) gets attributed
    // to the right chat instead of always the hardcoded "default" one.
    public async Task SendActiveChatAsync(string chatId)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetActiveChat = new SetActiveChat { ChatId = chatId }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendProviderAsync(string provider, string? model = null)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetProvider = new SetProvider { Provider = provider, Model = model ?? string.Empty }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task<ModelCatalog?> GetModelCatalogAsync()
    {
        if (_client == null) return null;
        try
        {
            return await _client.GetModelCatalogAsync(new Empty());
        }
        catch (Exception)
        {
            return null;
        }
    }

    public async Task SendMicrophoneDeviceAsync(string device)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetMicrophoneDevice = new SetMicrophoneDevice { Device = device }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendSpeakerDeviceAsync(string device)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetSpeakerDevice = new SetSpeakerDevice { Device = device }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendSetLanguageAsync(string language)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                SetLanguage = new SetLanguage { Language = language }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task<MicrophoneDeviceList?> GetMicrophoneDevicesAsync()
    {
        if (_client == null) return null;
        try
        {
            return await _client.GetMicrophoneDevicesAsync(new Empty());
        }
        catch (Exception)
        {
            return null;
        }
    }

    public async Task<SpeakerDeviceList?> GetSpeakerDevicesAsync()
    {
        if (_client == null) return null;
        try
        {
            return await _client.GetSpeakerDevicesAsync(new Empty());
        }
        catch (Exception)
        {
            return null;
        }
    }

    public async Task<string> GetSystemInfoAsync()
    {
        if (_client == null) return "—";
        try
        {
            var info = await _client.GetSystemInfoAsync(new Empty());
            return $"{info.Os} · {info.Cpu}";
        }
        catch (Exception)
        {
            return "—";
        }
    }

    public async Task<(bool Success, string Message)> SetApiKeyAsync(string provider, string apiKey)
    {
        if (_client == null) return (false, "Nicht verbunden.");
        try
        {
            var response = await _client.SetApiKeyAsync(new ApiKeyRequest
            {
                Provider = provider,
                ApiKey = apiKey,
            });
            return (response.Success, response.Message);
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }

    public async Task<MemorySummary?> GetMemorySummaryAsync(string search = "")
    {
        if (_client == null) return null;
        try
        {
            return await _client.GetMemorySummaryAsync(new MemoryQuery { Search = search });
        }
        catch (Exception)
        {
            return null;
        }
    }

    public async Task<(bool Success, int Count, string Message)> ImportMemoryAsync(string jsonText)
    {
        if (_client == null) return (false, 0, "Nicht verbunden.");
        try
        {
            var response = await _client.ImportMemoryAsync(new ImportMemoryRequest { JsonText = jsonText });
            return (response.Success, response.ImportedCount, response.Message);
        }
        catch (Exception ex)
        {
            return (false, 0, ex.Message);
        }
    }

    /// <summary>Phase B: blockiert bis zu ~45s (grosszügig über dem lowest-
    /// eagerness-Stille-Timeout + Extensions) auf eine einzelne diktierte
    /// Äußerung - KEIN Wake-Word/Konversations-Loop, sondern ein einmaliger
    /// Aufruf fürs Chat-Textfeld.</summary>
    public async Task<(bool Success, string Text, string Error)> DictateAsync(string eagerness)
    {
        if (_client == null) return (false, "", "Nicht verbunden.");
        try
        {
            var response = await _client.DictateAsync(
                new DictateRequest { Eagerness = eagerness },
                deadline: DateTime.UtcNow.AddSeconds(45));
            return (response.Success, response.Text, response.Error);
        }
        catch (Exception ex)
        {
            return (false, "", ex.Message);
        }
    }

    public async Task<System.Collections.Generic.Dictionary<string, bool>> GetApiKeyStatusAsync()
    {
        if (_client == null) return new();
        try
        {
            var response = await _client.GetApiKeyStatusAsync(new Empty());
            return new System.Collections.Generic.Dictionary<string, bool>(response.Configured);
        }
        catch (Exception)
        {
            return new();
        }
    }

    public async Task SendCancelChatAsync()
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                CancelChat = new CancelChat()
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    public async Task SendPermissionResponseAsync(string requestId, bool approved, bool persistent)
    {
        if (_stream == null || !_isConnected) return;
        try
        {
            await _stream.RequestStream.WriteAsync(new ClientMessage
            {
                PermissionResponse = new PermissionResponse
                {
                    RequestId = requestId,
                    Approved = approved,
                    Persistent = persistent,
                }
            });
        }
        catch (Exception)
        {
            SetConnected(false);
        }
    }

    private async Task ReadLoopWithReconnectAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                if (_stream == null) break;
                await foreach (var message in _stream.ResponseStream.ReadAllAsync(ct))
                {
                    Dispatch(() => HandleMessage(message));
                }
                // Stream ended cleanly — backend might have shut down
                SetConnected(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (RpcException ex) when (ex.StatusCode == StatusCode.Unavailable ||
                                          ex.StatusCode == StatusCode.Internal)
            {
                SetConnected(false);
                Dispatch(() => OnStatusChanged?.Invoke("Verbindung verloren — Reconnect..."));
            }
            catch (Exception ex)
            {
                SetConnected(false);
                Dispatch(() => OnStatusChanged?.Invoke($"Fehler: {ex.Message}"));
            }

            if (ct.IsCancellationRequested) break;

            // Exponential backoff
            _reconnectAttempts++;
            var delay = Math.Min(
                BaseReconnectDelayMs * (1 << Math.Min(_reconnectAttempts - 1, 10)),
                MaxReconnectDelayMs);

            Dispatch(() => OnStatusChanged?.Invoke(
                $"Reconnect in {delay / 1000}s (Versuch {_reconnectAttempts})..."));

            try
            {
                await Task.Delay(delay, ct);
            }
            catch (OperationCanceledException)
            {
                break;
            }

            // Attempt reconnect
            try
            {
                var address = $"http://{_host}:{_port}";
                _stream?.Dispose();
                _channel?.Dispose();
                _channel = GrpcChannel.ForAddress(address, new GrpcChannelOptions
                {
                    MaxReceiveMessageSize = 16 * 1024 * 1024,
                    MaxSendMessageSize = 16 * 1024 * 1024,
                });
                _client = new Tarno.TarnoClient(_channel);
                _stream = _client.Stream();
                SetConnected(true);
                _reconnectAttempts = 0;
                Dispatch(() => OnStatusChanged?.Invoke("Verbunden"));
            }
            catch (Exception)
            {
                // Will retry in next iteration
            }
        }
    }

    private void SetConnected(bool connected)
    {
        if (_isConnected == connected) return;
        _isConnected = connected;
        Dispatch(() => OnConnectionStateChanged?.Invoke(connected));
    }

    private void HandleMessage(ServerMessage message)
    {
        switch (message.PayloadCase)
        {
            case ServerMessage.PayloadOneofCase.ChatMessage:
                OnMessageReceived?.Invoke(
                    message.ChatMessage.Role,
                    message.ChatMessage.Text,
                    message.ChatMessage.ChatId,
                    message.ChatMessage.Id);
                break;
            case ServerMessage.PayloadOneofCase.Status:
                OnStatusChanged?.Invoke(message.Status.State);
                break;
            case ServerMessage.PayloadOneofCase.VoiceState:
                OnVoiceStateChanged?.Invoke(message.VoiceState.State.ToString());
                break;
            case ServerMessage.PayloadOneofCase.Log:
                OnLogReceived?.Invoke(message.Log.Level, message.Log.Message, message.Log.Module, message.Log.Timestamp);
                break;
            case ServerMessage.PayloadOneofCase.Task:
                OnTaskUpdate?.Invoke(
                    message.Task.Id,
                    message.Task.Title,
                    message.Task.Progress);
                break;
            case ServerMessage.PayloadOneofCase.Thinking:
                OnThinkingUpdate?.Invoke(
                    message.Thinking.Active,
                    message.Thinking.Stage,
                    message.Thinking.Reasoning,
                    message.Thinking.StageKey);
                break;
            case ServerMessage.PayloadOneofCase.PermissionRequest:
                OnPermissionRequested?.Invoke(
                    message.PermissionRequest.RequestId,
                    message.PermissionRequest.Permission,
                    message.PermissionRequest.Target,
                    message.PermissionRequest.RiskLevel,
                    message.PermissionRequest.SafetyPhrase);
                break;
            case ServerMessage.PayloadOneofCase.ContextUsage:
                OnContextUsageUpdate?.Invoke(message.ContextUsage.Used, message.ContextUsage.Max);
                break;
            case ServerMessage.PayloadOneofCase.AutonomyModeUpdate:
                OnAutonomyModeChanged?.Invoke(message.AutonomyModeUpdate.Mode);
                break;
            case ServerMessage.PayloadOneofCase.ReasoningModeUpdate:
                OnReasoningModeChanged?.Invoke(
                    message.ReasoningModeUpdate.Enabled,
                    message.ReasoningModeUpdate.Effort);
                break;
            case ServerMessage.PayloadOneofCase.ProviderUpdate:
                OnProviderChanged?.Invoke(
                    message.ProviderUpdate.Provider,
                    message.ProviderUpdate.Success,
                    message.ProviderUpdate.Message,
                    message.ProviderUpdate.Model);
                break;
            case ServerMessage.PayloadOneofCase.HighTierModelUpdate:
                OnHighTierModelChanged?.Invoke(message.HighTierModelUpdate.Enabled);
                break;
            case ServerMessage.PayloadOneofCase.SpeakResponsesUpdate:
                OnSpeakResponsesChanged?.Invoke(message.SpeakResponsesUpdate.Enabled);
                break;
            case ServerMessage.PayloadOneofCase.ContextEfficiencyUpdate:
                OnContextEfficiencyChanged?.Invoke(message.ContextEfficiencyUpdate.Enabled);
                break;
            case ServerMessage.PayloadOneofCase.PoolMessage:
                OnPoolMessageReceived?.Invoke(new PoolMessageEventArgs(
                    message.PoolMessage.FromAgent,
                    message.PoolMessage.ToAgent,
                    message.PoolMessage.Kind,
                    message.PoolMessage.Text,
                    message.PoolMessage.TimestampMs,
                    message.PoolMessage.ChatId,
                    message.PoolMessage.SubTaskId));
                break;
            case ServerMessage.PayloadOneofCase.PoolTaskResponse:
                OnPoolTaskCompleted?.Invoke(
                    message.PoolTaskResponse.Success,
                    message.PoolTaskResponse.Summary,
                    message.PoolTaskResponse.Error,
                    message.PoolTaskResponse.ChatId);
                break;
            case ServerMessage.PayloadOneofCase.MicrophoneDeviceUpdate:
                OnMicrophoneDeviceChanged?.Invoke(
                    message.MicrophoneDeviceUpdate.ActiveDevice,
                    message.MicrophoneDeviceUpdate.Loading,
                    message.MicrophoneDeviceUpdate.Status);
                break;
            case ServerMessage.PayloadOneofCase.SpeakerDeviceUpdate:
                OnSpeakerDeviceChanged?.Invoke(
                    message.SpeakerDeviceUpdate.ActiveDevice,
                    message.SpeakerDeviceUpdate.Loading,
                    message.SpeakerDeviceUpdate.Status);
                break;
            case ServerMessage.PayloadOneofCase.VisionStatusUpdate:
                OnVisionStatusChanged?.Invoke(
                    message.VisionStatusUpdate.CameraActive,
                    message.VisionStatusUpdate.VisionAvailable);
                break;
            case ServerMessage.PayloadOneofCase.SpeechEnvelope:
                OnSpeechEnvelope?.Invoke(
                    System.Linq.Enumerable.ToArray(message.SpeechEnvelope.Levels),
                    message.SpeechEnvelope.DurationSeconds);
                break;
            case ServerMessage.PayloadOneofCase.VisionImage:
                OnVisionImageReceived?.Invoke(
                    message.VisionImage.ImageBytes.ToByteArray(),
                    message.VisionImage.Caption);
                break;
            case ServerMessage.PayloadOneofCase.AgentTrace:
                OnAgentTrace?.Invoke(message.AgentTrace);
                break;
            case ServerMessage.PayloadOneofCase.CodingOutput:
                OnCodingOutput?.Invoke(
                    message.CodingOutput.Kind,
                    message.CodingOutput.Text,
                    message.CodingOutput.ChatId);
                break;
            case ServerMessage.PayloadOneofCase.LanguageChanged:
                OnLanguageChanged?.Invoke(
                    message.LanguageChanged.Language,
                    message.LanguageChanged.Success,
                    message.LanguageChanged.Message);
                break;
        }
    }

    private void Dispatch(Action action)
    {
        if (_dispatcher != null)
        {
            _dispatcher.TryEnqueue(() => action());
        }
        else
        {
            action();
        }
    }

    public void Dispose()
    {
        _cts?.Cancel();
        _stream?.Dispose();
        _channel?.Dispose();
        _cts?.Dispose();
    }
}
