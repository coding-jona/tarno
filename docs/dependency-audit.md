# TARNO – Dependency Audit

**Stand:** 2025-07-13 | **Phase:** 1 – Analyse

## Python-Environment

- **Python:** 3.12
- **Installierte Packages:** 108
- **Direkte Dependencies:** 31 (requirements.txt)

## Bundle-Größenanalyse (PyInstaller `_internal/`)

| Package | Größe | Genutzt von | Bewertung |
|---|---|---|---|
| **PySide6** | 92 MB | Legacy-UI (`tarno/ui/app.py`) | ❌ ENTFERNEN (ADR-002) |
| **av.libs** | 63 MB | OVOS (Audio-Transcoding) | ❌ ENTFERNEN mit OVOS |
| **ctranslate2** | 59 MB | faster-whisper (STT) | ✅ BEIBEHALTEN (Kern-Feature) |
| **scipy** | 46 MB | OVOS, sklearn | ⚠️ PRÜFEN ob direkt genutzt |
| **speech_recognition** | 43 MB | Recognizer (`tarno/voice/recognizer.py`) | ✅ BEIBEHALTEN |
| **onnxruntime** | 34 MB | openWakeWord (Wake-Word) | ✅ BEIBEHALTEN |
| **openWakeWord** | 22 MB | Wake-Word-Erkennung | ✅ BEIBEHALTEN |
| **numpy + numpy.libs** | 26 MB | Überall (Audio, ML) | ✅ BEIBEHALTEN |
| **scipy.libs** | 19 MB | scipy-Abhängigkeit | ⚠️ MIT scipy PRÜFEN |
| **PIL (Pillow)** | 13 MB | Screenshot, Bildverarbeitung | ✅ BEIBEHALTEN |
| **sklearn** | 12 MB | OVOS-Dependency | ❌ ENTFERNEN mit OVOS |
| **cryptography** | 9 MB | Secrets-Vault (Fernet) | ✅ BEIBEHALTEN |
| **hf_xet** | 9 MB | HuggingFace-Tokenizer | ⚠️ Optional |
| **pygame** | 7 MB | TTS-Playback | ✅ BEIBEHALTEN |
| **tokenizers** | 7 MB | HuggingFace-Provider | ⚠️ Optional |
| **numpy** | 6 MB | Core-Dependency | ✅ BEIBEHALTEN |
| **rapidfuzz** | 6 MB | OVOS (Text-Matching) | ❌ ENTFERNEN mit OVOS |

## Erwartete Größenreduktion nach ADR-002

| Maßnahme | Einsparung |
|---|---|
| PySide6 entfernen | -92 MB |
| OVOS-Stack entfernen | -80 MB (av.libs, OVOS-Packages) |
| scipy + sklearn entfernen | -78 MB |
| rapidfuzz entfernen | -6 MB |
| **Gesamt** | **~256 MB** |

**Aktuelle Bundle-Größe:** 503 MB (`_internal/`) + 127 MB (UI) + 58 MB (Runtimes) = 710 MB  
**Erwartete Größe nach Optimierung:** ~454 MB → ~200 MB nach NSIS-Kompression

## WinUI 3 Dependencies

| Package | Version | Zweck |
|---|---|---|
| Microsoft.WindowsAppSDK | 1.7.250606001 | WinUI 3 Framework |
| Microsoft.Windows.SDK.BuildTools | 10.0.26100.1742 | Windows APIs |
| Grpc.Net.Client | 2.62.0 | gRPC-Client |
| Google.Protobuf | 3.27.0 | Proto-Serialisierung |
| CommunityToolkit.Mvvm | 8.2.2 | MVVM-Toolkit |
| Microsoft.Web.WebView2 | 1.0.2903.40 | WebView2 (Hybrid-UI) |

**Bewertung:** Alle WinUI-Dependencies sind notwendig und aktuell.

## Fehlende Dependencies

| Package | Status | Anmerkung |
|---|---|---|
| `grpcio` | NICHT installiert (pip) | Wird nur im Backend benötigt, installiert via PyInstaller hidden-import |
| `anthropic` | NICHT installiert | Claude-Provider nicht nutzbar ohne manuelles `pip install` |
| `openwakeword` | NICHT installiert (pip) | Wird über lokalen Pfad (`openWakeWord-0.6.0/`) geladen |

## Empfehlungen

1. **Sofort (Phase 2):** PySide6 und OVOS aus `tarno.spec` entfernen
2. **Phase 3:** `requirements-dev.txt` erstellen (pytest, coverage, mypy)
3. **Phase 7:** HuggingFace-Dependencies optional machen (hf_xet, tokenizers)
4. **Laufend:** Dependencies auf Sicherheitslücken prüfen (`pip audit`)
