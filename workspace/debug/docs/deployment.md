# TARNO Deployment & Release Guide

## Requirements

- Python 3.11 or 3.12
- Windows 10/11, macOS or Linux
- Microphone access (voice mode)
- API key for at least one LLM provider (OpenAI, Anthropic, Groq, etc.)

## Installation from Source

```powershell
# Clone / entpacken
cd openWakeWord-0.6.0

# Virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\activate

# Dependencies (liegt unter workspace/installer/)
pip install -r workspace/installer/requirements.txt

# Konfiguration anlegen
python -c "from tarno.core.config import TarnoConfig; TarnoConfig.load().save()"
```

Edit `~/.tarno/config/tarno_config.yaml` to set API keys and provider.

## Running

```powershell
# Voice mode
python -m tarno --voice

# Text mode
python -m tarno --text

# OVOS bus mode
python -m tarno --no-gui

# Qt GUI mode (default)
python -m tarno
```

## Building the Installer (Windows)

The installer is a separate subproject under `installer/`. It produces a PyInstaller-based application payload and will later build a custom PySide6 hologram installer wizard.

```powershell
# Build the application payload (dry-run)
python -m installer.payload.build_payload --dry-run

# Build the application payload for real
python -m installer.payload.build_payload

# Orchestrate the full installer build (currently payload only)
python -m installer.pipeline.build_all --dry-run
```

The legacy scripts `scripts/build_installer.py` and `scripts/tarno_installer.iss` are kept only as references and are no longer the canonical build path.

## Auto-Updater

The updater checks the GitHub release endpoint configured in `tarno/updater.py`.
Set the repository slug and current version before shipping:

```python
AutoUpdater(current_version="0.2.0", repo="owner/tarno")
```

## CI/CD

The GitHub Actions workflow in `.github/workflows/ci.yml` runs tests and lint on every push.
Installer-specific CI/CD workflows will be added under `installer/pipeline/`.

## Security Notes

- Secrets are stored via the secrets vault (`tarno/security/secrets.py`).
- PII redaction can be enabled with `security.pii_redaction_enabled: true`.
- Audit logs are verified on shutdown; retention is 365 days by default.

## First-Start Wizard

After installation the installer launches the TARNO first-start wizard automatically:

```powershell
.\tarno.exe --first-start
```

The wizard guides the user through:

- Hardware and audio detection
- Whisper model selection
- Wake-word selection
- Privacy settings
- LLM provider / API-key configuration
- Model downloads (when URLs are configured)

Configuration is saved to `%LOCALAPPDATA%\.tarno\config\tarno_config.yaml`.

## AI Model Management

The core ships a `tarno.model_manager.ModelManager` that handles downloads,
SHA-256 verification and resume support. Models are stored under:

```
%LOCALAPPDATA%\.tarno\models
```

A list of required models can be defined in `config/default.yaml` under the
`models` key. Example:

```yaml
models:
  - name: whisper-small
    filename: whisper-small.bin
    url: https://example.com/whisper-small.bin
    sha256: abc123...
```
