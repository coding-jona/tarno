## Analyse: Settings-Seite mit LLM-Provider-Wechsel via gRPC

### Aktueller Stand

Die **SettingsPage** existiert bereits (`src/JARVIS.UI/Pages/SettingsPage.xaml`) mit drei UI-only Karten: KI-Provider (ComboBox mit Mistral/Claude/Ollama), Erscheinungsbild und Autostart. Allerdings ist die Seite rein statisch -- kein ViewModel-Binding, kein Code-Behind ausser `InitializeComponent()`, und die ComboBox zeigt nur 3 der 6 verfuegbaren Provider.

Auf der Backend-Seite:
- **Config-System** (`jarvis/core/config.py`): `LLMConfig.provider` akzeptiert 6 Werte: `mistral`, `claude`, `ollama`, `gemini`, `huggingface`, `groq`. `JarvisConfig.save()` persistiert nach YAML.
- **gRPC-Proto** (`jarvis/grpc/jarvis.proto`): Kein Settings-RPC vorhanden. Es gibt `CommandRequest` (name + params Map), das als generischer Kanal nutzbar waere.
- **gRPC-Server** (`jarvis/grpc/server.py`): `handle_command_request()` leitet Commands an `engine.tools.execute()` weiter -- nicht an Config. Das muesste erweitert werden.
- **MainViewModel**: Kein Property fuer den aktuellen Provider, kein Binding zur SettingsPage.

### Vorgeschlagener Ansatz

**Option A (empfohlen): Dedizierter unary RPC `UpdateSettings` / `GetSettings`**

Ein eigener RPC ist sauberer als Commands durch den bidirektionalen Stream zu tunneln, weil Settings-Aenderungen Request/Response-Semantik haben (der Client will wissen, ob die Aenderung erfolgreich war).

**Option B (verworfen): CommandRequest missbrauchen**

`CommandRequest` koennte theoretisch `name="set_provider", params={"provider": "claude"}` senden. Problem: Kein typisiertes Response, keine Fehlerbehandlung, und `handle_command_request` routet aktuell an `ToolRegistry`, nicht an Config. Der Workaround waere haesslich und wuerde das Command-System fuer etwas zweckentfremden, wofuer es nicht gedacht ist.

**Option C (verworfen): Einstellungen nur lokal im WinUI speichern**

Wuerde das Backend nicht informieren -- der Provider-Wechsel wuerde erst nach Neustart greifen, und die WinUI-Config waere nicht synchron mit der Python-Config.

### Implementierungsplan (Option A)

#### Schritt 1: Proto erweitern (`jarvis/grpc/jarvis.proto`)

```protobuf
// Neue Messages
message SettingsRequest {}

message SettingsResponse {
  string llm_provider = 1;
  repeated string available_providers = 2;
}

message UpdateSettingsRequest {
  string llm_provider = 1;
}

message UpdateSettingsResponse {
  bool success = 1;
  string error = 2;
}

// Im service Jarvis:
rpc GetSettings (SettingsRequest) returns (SettingsResponse);
rpc UpdateSettings (UpdateSettingsRequest) returns (UpdateSettingsResponse);
```

Alle 6 Provider (`mistral`, `claude`, `gemini`, `huggingface`, `groq`, `ollama`) kommen als `available_providers` zurueck, damit die UI nicht hardcoden muss, welche es gibt.

#### Schritt 2: Python gRPC-Server erweitern (`jarvis/grpc/server.py`)

- `JarvisGrpcServicer.GetSettings()`: Liest `self.bridge.config.llm.provider` und gibt die Liste der verfuegbaren Provider zurueck.
- `JarvisGrpcServicer.UpdateSettings()`: Setzt `self.bridge.config.llm.provider`, ruft `config.save()` auf den User-Config-Pfad (`~/.jarvis/config/jarvis_config.yaml`) auf. Der laufende Engine-Provider muss **nicht** hot-swapped werden (das wuerde erhebliche Komplexitaet hinzufuegen) -- ein Hinweis in der UI, dass ein Neustart noetig ist, reicht fuer v0.2.

#### Schritt 3: C# gRPC-Client erweitern (`src/JARVIS.UI/Services/GrpcClientService.cs`)

Zwei neue Methoden:
- `GetSettingsAsync()` -> ruft `GetSettings` RPC auf
- `UpdateSettingsAsync(string provider)` -> ruft `UpdateSettings` RPC auf

#### Schritt 4: ViewModel erweitern (`src/JARVIS.UI/ViewModels/MainViewModel.cs`)

Neue Properties:
- `SelectedProvider` (string, ObservableProperty)
- `AvailableProviders` (ObservableCollection<string>)
- `SaveSettingsCommand` (RelayCommand)

Beim Navigieren zur SettingsPage: `GetSettingsAsync()` aufrufen, um den aktuellen Provider zu laden.

#### Schritt 5: SettingsPage XAML aktualisieren (`src/JARVIS.UI/Pages/SettingsPage.xaml`)

- ComboBox an `AvailableProviders` binden statt hartcodierter Items
- `SelectedItem` an `SelectedProvider` binden
- `SelectionChanged` oder Command loest `UpdateSettingsAsync` aus
- Alle 6 Provider anzeigen mit deutschen Labels: Mistral (Standard), Claude, Gemini, HuggingFace, Groq, Ollama (lokal)
- InfoBar oder TextBlock mit Hinweis "Aenderungen werden nach Neustart wirksam"

### Betroffene Komponenten

| Datei | Aenderung |
|-------|-----------|
| `jarvis/grpc/jarvis.proto` | 4 neue Messages, 2 neue RPCs |
| `jarvis/grpc/server.py` | `GetSettings` + `UpdateSettings` Implementierung, Config-Persistenz |
| `src/JARVIS.UI/Services/GrpcClientService.cs` | 2 neue Methoden |
| `src/JARVIS.UI/ViewModels/MainViewModel.cs` | Provider-Properties, Load/Save-Logik |
| `src/JARVIS.UI/Pages/SettingsPage.xaml` | Data-Binding statt statischer Items |
| `src/JARVIS.UI/Pages/SettingsPage.xaml.cs` | ViewModel-Zugriff, evtl. OnNavigatedTo |

### Risiken und Hinweise

- **Proto-Regenerierung**: Nach Proto-Aenderung muessen sowohl die Python-Stubs (`grpc_tools.protoc`) als auch die C#-Stubs (automatisch via `Grpc.Tools` NuGet beim Build) neu generiert werden.
- **Hot-Swap des Providers**: Aktuell nicht geplant. Die Engine instantiiert den Provider beim Start. Ein Runtime-Wechsel wuerde erfordern, dass `JarvisEngine` den Provider neu erstellt und die Conversation-History migriert -- das ist ein separates Feature.
- **Ollama-Sonderbehandlung**: Bei Auswahl von Ollama sollte die UI darauf hinweisen, dass Ollama lokal laufen muss (`num_gpu: 0`, CPU-only).
