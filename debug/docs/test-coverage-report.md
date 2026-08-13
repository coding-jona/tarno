# TARNO – Test-Coverage-Bericht

**Stand:** 2025-07-13 | **Phase:** 1 – Analyse

## Übersicht

| Metrik | Wert |
|---|---|
| Codebasis | 18.005 Zeilen (144 Python, 15 C#, 14 XAML) |
| Test-Dateien | 14 |
| Test-Funktionen | 137 |
| Test-Framework | pytest (nicht installiert in Prod-Umgebung) |

## Test-Verteilung nach Modul

| Testdatei | Tests | Abgedecktes Modul | Bewertung |
|---|---|---|---|
| `test_core.py` | 33 | Engine, Config, Events | ★★★★☆ Gut |
| `test_command_engine.py` | 14 | CommandEngine, RiskLevel | ★★★★☆ Gut |
| `test_security.py` | 14 | SecretsVault, Audit, PII, Encryption | ★★★★☆ Gut |
| `test_integrations.py` | 13 | Calendar, Discord, Git, Smart-Home, Minecraft | ★★★☆☆ Basis |
| `test_voice.py` | 11 | WakeWord, Recognizer, Synthesizer | ★★★☆☆ Basis |
| `test_voice_architecture.py` | 12 | VoiceController, AudioStream, EchoProtection | ★★★☆☆ Basis |
| `test_memory.py` | 11 | MemoryStore, Retrieval, Privacy | ★★★☆☆ Basis |
| `test_extensions.py` | 9 | Scheduler, Reminders, Routines, TaskPlanner | ★★★☆☆ Basis |
| `test_streaming.py` | 5 | StreamingResponse | ★★☆☆☆ Minimal |
| `test_plugins.py` | 4 | PluginManager, Base | ★★☆☆☆ Minimal |
| `test_memory_integration.py` | 3 | Memory + Conversation | ★★☆☆☆ Minimal |
| `test_model_manager.py` | 3 | ModelManager | ★★☆☆☆ Minimal |
| `test_updater.py` | 3 | Updater | ★★☆☆☆ Minimal |
| `test_summarizer.py` | 2 | ConversationSummarizer | ★☆☆☆☆ Minimal |

## Nicht abgedeckte Bereiche

### Kritisch (keine Tests)

| Bereich | Dateien | Risiko |
|---|---|---|
| **gRPC Server/Bridge** | `tarno/grpc/server.py` (410 Zeilen) | Hoch – Kernkommunikation |
| **gRPC Mock-Engine** | `tarno/grpc/mock_engine.py` (218 Zeilen) | Mittel |
| **WinUI Frontend** | Alle C#/XAML-Dateien (2.437 Zeilen) | Hoch – keine Unit-Tests |
| **AI Provider** | Alle Client-Dateien (keine Mocking-Tests) | Hoch – API-Calls |
| **Installer** | NSIS-Script, Build-Scripts | Mittel |

### Mittel (unzureichende Tests)

| Bereich | Vorhandene Tests | Fehlend |
|---|---|---|
| Voice Pipeline | 23 Tests | End-to-End Wake→STT→LLM→TTS |
| Conversation | Indirekt via test_core | Token-Counting, History-Trim |
| Config | Indirekt via test_core | Corruption-Recovery, Deep-Merge Edge Cases |
| Permission Service | Indirekt via test_command_engine | UI-Dialog-Integration |

## Empfehlungen

### Phase 2 (Stabilisierung)
1. `requirements-dev.txt` erstellen mit `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`
2. gRPC-Server-Tests mit Mock-Client
3. VoiceController-Integrationstests mit simuliertem AudioStream

### Phase 3 (Security)
4. SecretsVault End-to-End Test (Keyring + Fallback)
5. Config-Corruption-Recovery Test

### Phase 4 (Command Engine)
6. Permission-Service mit simuliertem Dialog
7. Command-Execution End-to-End

### Phase 5 (UI)
8. WinUI Unit-Tests mit MSTest/xUnit (optional, da UI schwer testbar)
9. UI-Interaction-Tests via WinAppDriver (optional)

### Ziel-Coverage

| Phase | Ziel |
|---|---|
| Aktuell | ~40% (geschätzt, Python-Backend only) |
| Phase 2 | 60% |
| Phase 4 | 75% |
| Release | 80%+ |
