# Analyse und Implementierungsplan: Settings-Seite mit LLM-Provider-Wechsel

## Ist-Zustand

### WinUI Frontend
- Es existiert bereits eine **SettingsPage** (`src/JARVIS.UI/Pages/SettingsPage.xaml`) mit einer ComboBox "KI-Provider" (Mistral, Claude, Ollama). Allerdings ist die Page rein statisch -- der Code-Behind (`SettingsPage.xaml.cs`) ist leer, es gibt kein Data Binding und keine Logik zum Senden der Auswahl.

### gRPC-Schnittstelle
- Die Proto-Datei (`jarvis/grpc/jarvis.proto`) definiert eine bidirektionale Stream-RPC und eine unary `GetSystemInfo`-RPC.
- Es gibt bereits einen **`CommandRequest`**-Nachrichtentyp im `ClientMessage` oneof mit `name` und `params` (map<string,string>). Dieser wird im Backend in `JarvisGrpcBridge.handle_command_request()` verarbeitet und an die Tool-Registry weitergeleitet.
- Der `GrpcClientService` im C#-Frontend hat bisher keine Methode zum Senden von `CommandRequest`.

### Backend-Konfiguration
- `jarvis/core/config.py` hat eine `LLMConfig`-Klasse mit `provider`-Feld (Werte: "mistral", "gemini", "huggingface", "groq", "ollama", "claude").
- `JarvisConfig` hat eine `save(path)` Methode, die die gesamte Config als YAML persistiert.
- User-Config wird unter `~/.jarvis/config/jarvis_config.yaml` gespeichert.

## Implementierungsplan

### Schritt 1: Proto erweitern (optional, aber empfohlen)

Man kann den bestehenden `CommandRequest`-Mechanismus nutzen (z.B. `name="set_llm_provider"`, `params={"provider": "claude"}`), aber sauberer waere ein dedizierter RPC. Zwei Optionen:

**Option A -- CommandRequest wiederverwenden (minimal, kein Proto-Rebuild noetig):**
Einfach `CommandRequest` mit `name="set_llm_provider"` senden. Vorteil: kein Protobuf-Rebuild. Nachteil: kein typsicherer Rueckgabewert, keine GetSettings-Abfrage.

**Option B -- Dedizierte RPCs (sauberer):**
```protobuf
service Jarvis {
  rpc Stream (...) returns (...);
  rpc GetSystemInfo (...) returns (...);
  rpc GetSettings (Empty) returns (SettingsResponse);
  rpc UpdateSettings (UpdateSettingsRequest) returns (UpdateSettingsResponse);
}

message UpdateSettingsRequest {
  string llm_provider = 1;  // "mistral", "claude", "ollama", etc.
}

message UpdateSettingsResponse {
  bool success = 1;
  string error = 2;
}

message SettingsResponse {
  string llm_provider = 1;
}
```

**Empfehlung:** Option A fuer schnelle Umsetzung, da `CommandRequest` bereits existiert und im Backend geroutet wird.

### Schritt 2: Backend -- Command-Handler fuer Provider-Wechsel

In `jarvis/grpc/server.py` die Methode `handle_command_request` erweitern oder einen dedizierten Handler registrieren:

```python
def handle_command_request(self, command: jarvis_pb2.CommandRequest) -> None:
    if command.name == "set_llm_provider":
        provider = command.params.get("provider", "")
        valid = {"mistral", "claude", "ollama", "gemini", "groq", "huggingface"}
        if provider not in valid:
            self._broadcast(self._make_chat_message("assistant", f"Unbekannter Provider: {provider}"))
            return
        self.config.llm.provider = provider
        user_config_path = Path.home() / ".jarvis" / "config" / "jarvis_config.yaml"
        self.config.save(user_config_path)
        self.engine.reload_llm_provider()  # muss implementiert werden
        self._broadcast(self._make_chat_message("assistant", f"LLM-Provider auf {provider} gewechselt."))
        return
    elif command.name == "get_settings":
        self._broadcast(self._make_chat_message("assistant", f"llm_provider:{self.config.llm.provider}"))
        return
    # Bestehende Logik
    result = self.engine.tools.execute(command.name, dict(command.params))
    self._broadcast(self._make_chat_message("assistant", f"{result}"))
```

Ausserdem muss im `JarvisEngine` eine Methode `reload_llm_provider()` erstellt werden, die den aktiven LLM-Client basierend auf `config.llm.provider` neu instanziiert.

### Schritt 3: C# GrpcClientService erweitern

Eine neue Methode zum Senden von CommandRequests:

```csharp
public async Task SendCommandAsync(string name, Dictionary<string, string> parameters)
{
    if (_stream == null) return;
    var command = new CommandRequest { Name = name };
    foreach (var kvp in parameters)
        command.Params.Add(kvp.Key, kvp.Value);

    await _stream.RequestStream.WriteAsync(new ClientMessage { Command = command });
}
```

### Schritt 4: SettingsPage mit Logik versehen

**XAML-Aenderungen** -- ComboBox bekommt `x:Name` und `SelectionChanged`-Event, Provider-Liste wird um die fehlenden Eintraege ergaenzt:

```xml
<ComboBox x:Name="ProviderComboBox"
          Style="{StaticResource JARVISComboBoxStyle}"
          Margin="0,8,0,0"
          SelectionChanged="OnProviderSelectionChanged">
    <ComboBoxItem Content="Mistral (Standard)" Tag="mistral" />
    <ComboBoxItem Content="Claude" Tag="claude" />
    <ComboBoxItem Content="Ollama (lokal)" Tag="ollama" />
    <ComboBoxItem Content="Gemini" Tag="gemini" />
    <ComboBoxItem Content="Groq" Tag="groq" />
    <ComboBoxItem Content="HuggingFace" Tag="huggingface" />
</ComboBox>
```

**Code-Behind:**

```csharp
public sealed partial class SettingsPage : Page
{
    private GrpcClientService? _grpcService;

    public SettingsPage()
    {
        this.InitializeComponent();
        // GrpcClientService muss per DI oder statisch zugaenglich sein
        _grpcService = App.GrpcService;
    }

    private async void OnProviderSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (sender is ComboBox combo && combo.SelectedItem is ComboBoxItem item)
        {
            var provider = item.Tag?.ToString() ?? "mistral";
            if (_grpcService != null)
            {
                await _grpcService.SendCommandAsync("set_llm_provider",
                    new Dictionary<string, string> { ["provider"] = provider });
            }
        }
    }
}
```

### Schritt 5: Initialen Provider beim Seitenaufruf laden

Beim Navigieren zur SettingsPage sollte der aktuelle Provider vom Backend abgefragt und die ComboBox entsprechend gesetzt werden. Das kann ueber einen `get_settings`-Command passieren, wobei die Antwort als ChatMessage zurueckkommt und geparst wird -- oder sauberer ueber einen dedizierten unary RPC (Option B).

## Zusammenfassung der zu aendernden Dateien

| Datei | Aenderung |
|---|---|
| `jarvis/grpc/server.py` | `handle_command_request` um `set_llm_provider` und `get_settings` erweitern |
| `jarvis/core/engine.py` | `reload_llm_provider()` Methode hinzufuegen |
| `src/JARVIS.UI/Services/GrpcClientService.cs` | `SendCommandAsync()` Methode hinzufuegen |
| `src/JARVIS.UI/Pages/SettingsPage.xaml` | ComboBox mit `x:Name`, `Tag`, `SelectionChanged` versehen; Provider-Liste erweitern |
| `src/JARVIS.UI/Pages/SettingsPage.xaml.cs` | Event-Handler und gRPC-Aufruf implementieren |
| `src/JARVIS.UI/App.xaml.cs` (oder DI) | `GrpcClientService` fuer SettingsPage zugaenglich machen |

## Offene Fragen

1. **Hot-Reload des Providers:** Soll der Provider-Wechsel sofort wirksam werden (Engine reloaded den LLM-Client), oder erst beim naechsten Neustart? Hot-Reload ist benutzerfreundlicher, erfordert aber eine `reload_llm_provider()`-Methode im Engine.
2. **Fehler-Feedback:** Wie soll die UI anzeigen, dass der Wechsel erfolgreich war oder fehlgeschlagen ist? Aktuell kaeme die Bestaetigung als ChatMessage -- ein dedizierter RPC mit Response waere sauberer.
3. **Vollstaendige Provider-Liste:** Sollen alle 6 Provider (mistral, claude, ollama, gemini, groq, huggingface) in der ComboBox erscheinen, oder nur eine Teilmenge?
