"""Centralized configuration system using dataclasses and YAML."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tarno_backend.utils.paths import CONFIG_DIR

log = logging.getLogger(__name__)


_CONFIG_DIR = CONFIG_DIR
_DEFAULT_CONFIG = _CONFIG_DIR / "default.yaml"
_USER_CONFIG_NAME = "tarno_config.yaml"

# Default TTS voice repositories mapped to the global language setting.
# These are used when the user has not manually overridden the voice.
_DEFAULT_TTS_VOICE = {
    "de": "Trelis/piper-de-de-thorsten-medium",
    "en": "Trelis/piper-en-us-ryan-medium",
}

# TTS-friendly prompt defaults per language. These are injected into the
# LLM system prompt and into SpeechNaturalizer so the assistant sounds right
# no matter which language is active.
_TTS_PROMPT_LANGUAGE_DEFAULTS = {
    "de": {
        "voice_hint": "thorsten",
        "filler_words": ["äh", "naja", "also", "hmm", "tja", "schau mal", "übrigens"],
        "connective_phrases": [
            "und dann", "außerdem", "was auch noch wichtig ist",
            "was ich sonst noch sagen wollte", "übrigens",
        ],
    },
    "en": {
        "voice_hint": "ryan",
        "filler_words": ["uh", "well", "so", "hmm", "yeah", "you know", "by the way"],
        "connective_phrases": [
            "and then", "also", "what's also important",
            "what else I wanted to say", "by the way",
        ],
    },
}


@dataclass
class VADConfig:
    engine: str = "silero"  # silero | energy
    silence_threshold_sec: float = 1.8
    min_speech_duration_sec: float = 0.3
    max_speech_duration_sec: float = 30.0
    trailing_extension_sec: float = 2.0
    max_extensions: int = 3
    energy_floor: float = 300.0
    noise_gate_enabled: bool = True
    onset_factor: float = 1.5
    listen_timeout: float = 10.0
    start_threshold: float = 0.5
    end_threshold: float = 0.35
    speech_pad_ms: int = 30


def vad_config_for_eagerness(eagerness: str) -> VADConfig:
    """Presets for the in-chat Diktat-Feature (Phase B) - deutlich
    großzügigere Stille-Toleranz als der normale Sprach-Loop (dort ist
    schnelle Antwortzeit wichtig; beim Diktat soll der Nutzer in Ruhe
    formulieren können, ohne mitten im Satz abgeschnitten zu werden).
    Unbekannter Wert fällt auf "medium" zurück."""
    presets = {
        "low": VADConfig(silence_threshold_sec=12.0, max_extensions=5, trailing_extension_sec=3.0),
        "medium": VADConfig(silence_threshold_sec=9.0, max_extensions=3, trailing_extension_sec=2.5),
        "high": VADConfig(silence_threshold_sec=5.0, max_extensions=2, trailing_extension_sec=1.5),
    }
    return presets.get(eagerness, presets["medium"])


@dataclass
class TTSPromptConfig:
    """Config knob for TTS-friendly prompt generation.

    Controls how the system prompt instructs the LLM to produce text that
    the Thorsten/Piper TTS voice can read naturally.
    """

    enabled: bool = True
    spoken_style: bool = True
    max_sentence_words: int = 14
    filler_words: list[str] = field(default_factory=lambda: [
        "äh", "naja", "also", "hmm", "tja", "schau mal", "übrigens"
    ])
    allow_fillers: bool = True
    prosody_punctuation: bool = True
    avoid_bullets: bool = True
    connective_phrases: list[str] = field(default_factory=lambda: [
        "und dann", "außerdem", "was auch noch wichtig ist",
        "was ich sonst noch sagen wollte", "übrigens"
    ])
    voice_hint: str = "thorsten"


@dataclass
class AudioConfig:
    # Lowered from 4000 (found live): with AGC active, the background-noise
    # floor after amplification sits around 700-900 RMS, and real speech
    # reliably reaches well into the thousands - 1500 gives clear separation
    # from the noise floor while triggering promptly on quiet/distant speech
    # that 4000 was missing (measured over an 11.5k-chunk live session).
    energy_threshold: int = 1500
    listen_timeout: int = 10
    phrase_time_limit: int = 15
    pause_threshold: float = 3.0
    language: str = "de"
    tts_engine: str = "piper"
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1280
    voice: str = "Trelis/piper-de-de-thorsten-medium"
    speed: float = 1.1
    tts_cache_dir: str = "~/.tarno/cache/tts"
    whisper_model: str = "small"
    whisper_initial_prompt: str = ""
    whisper_beam_size: int = 2
    whisper_condition_on_previous_text: bool = False
    vad_filter: bool = True
    microphone_device: str = "default"

    # Local TTS engine extensions
    voice_reference_path: str = ""
    voice_reference_text: str = ""
    tts_streaming: bool = True
    tts_stream_timeout_sec: float = 2.0
    tts_sentence_fallback: bool = True
    tts_output_device: str | None = None
    tts_prompt: TTSPromptConfig = field(default_factory=TTSPromptConfig)


@dataclass
class AGCConfig:
    """"Künstlicher Mikrofonverstärker": one shared gain stage used by BOTH
    wake-word listening (tarno/voice/wakeword.py) and the post-wake-word
    speech capture (tarno/voice/adaptive_listener.py) - found live: an
    earlier version only boosted the wake-word phase, so far-field wake-word
    activation worked but the actual command afterward was still captured at
    the original (unboosted) volume, defeating the point of far-field
    activation in the first place. Each consumer holds its own gain-state
    instance (tarno/voice/audio_utils.AutomaticGainControl) built from these
    shared target values, so the two don't fight over a shared EMA state.

    Higher target/max_gain values help genuine far-field range (~5m vs the
    ~20cm baseline) for low-amplitude-but-otherwise-clean signals; they do
    NOT fix poor signal-to-noise ratio from real room noise/reverb at
    distance - amplifying multiplies noise right along with the voice
    (verified live with a real recording at simulated distance)."""

    enabled: bool = True
    target_rms: float = 9000.0  # höhere Ziel-Lautstärke für Fernfeld (int16-Skala, max 32767)
    max_gain: float = 50.0  # deutlich mehr Verstärkung für >3m Distanz; deckelt Clipping ab
    attack: float = 0.5  # sanfte Anpassung der Verstärkung zwischen Chunks


@dataclass
class WakeWordConfig:
    enabled: bool = True
    backend: str = "vosk"  # vosk | openwakeword | porcupine
    model_name: str = "jarvis"  # openwakeword/porcupine Hinweis; Vosk nutzt wake_phrases
    picovoice_access_key: str = ""  # nur nötig bei backend: porcupine
    threshold: float = 0.10  # niedrig für Flüster-Erkennung, aber nicht so extrem, dass Rauschen feuert
    sensitivity: float = 0.9  # höher für Fernfeld-/leise "jarvis" (porcupine/openwakeword)
    inference_framework: str = "onnx"
    patience: int = 1
    debounce_time: float = 1.0
    confirm_wake_word: bool = False
    # Vosk: German-trained, offline, no API key - supports all 4 wake phrases
    # via grammar-constrained recognition (see tarno/voice/wakeword.py). The
    # small model's closed lexicon drops unlisted words (e.g. "tarno") from
    # the grammar entirely (verified live) - "large" trades ~1.9GB download +
    # more RAM/CPU for broader vocabulary coverage; user-selectable in
    # Settings, not downloaded until first selected.
    vosk_model_size: str = "small"  # small | large
    wake_phrases: list[str] = field(default_factory=lambda: [
        "hey jarvis", "hey javis", "hey jaavis",
        "hey tarno", "hey tano", "hey taano",
        "jarvis", "javis", "jaavis",
        "jarwis", "jarwiss", "jarviss",  # häufige Vosk-Fehler (w/v, doppeltes s)
        "tarno", "tano", "taano",
    ])  # includes r-dropped variants (German "r" is often swallowed/vocalized, especially by non-native speakers)


@dataclass
class BriefingConfig:
    enabled: bool = False
    times: list[str] = field(default_factory=list)
    trigger_on_start: bool = False
    prompt: str = (
        "Erstelle ein kurzes, motivierendes morgendliches Briefing im TARNO-Stil. "
        "Nutze die verfügbaren Systeminformationen und begrüße den Nutzer höflich. "
        "Halte es auf Deutsch, knapp und präzise."
    )
    calendar_file: str = ""
    calendar_days: int = 1


@dataclass
class ClaudeConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    max_history: int = 20
    timeout: float = 60.0
    max_retries: int = 3


@dataclass
class OllamaConfig:
    model: str = "tarno"
    base_url: str = "http://localhost:11434"
    num_ctx: int = 8192
    num_gpu: int = 0  # 0 = CPU-only (schneller auf AMD/Windows), -1 = GPU
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0


@dataclass
class GroqConfig:
    model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0
    rate_limit_rps: float = 0.0  # 0 = keine Drosselung


@dataclass
class HuggingFaceConfig:
    model: str = "Qwen/Qwen3-32B"
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0
    rate_limit_rps: float = 0.0  # 0 = keine Drosselung


@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash"
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0
    rate_limit_rps: float = 0.0  # 0 = keine Drosselung


@dataclass
class OpenAICompatibleConfig:
    """Configuration for any OpenAI-compatible chat-completions provider."""

    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0
    rate_limit_rps: float = 0.0  # 0 = keine Drosselung
    context_window: int = 128_000


@dataclass
class MistralDifficultyTiers:
    """Model per difficulty tier. low/medium are chosen automatically by
    MistralProvider's word-count heuristic, but ONLY while reasoning_effort
    (the "Denken"-Toggle) is active - see send()'s difficulty_enabled check.
    With Thinking off, every request uses the plain MistralConfig.model
    (mistral-small-2506) regardless of tier. high is NEVER auto-selected by
    the classifier (that used to mis-fire on ordinary messages containing
    tool-adjacent words like "Datei") - it's only reachable via the explicit
    "Starkes Modell"-toggle (TarnoEngine.use_high_tier_model).

    IDs and rate limits (2026-07-20, TPM = tokens/minute, RPS = requests/sec):
      low:    ministral-3b-2512   1.3M TPM / 12.50 RPS (fastest, cheapest)
      medium: mistral-small-2506  2.25M TPM / 5.00 RPS
      high:   mistral-medium-2508 356,250 TPM / 0.38 RPS (manual opt-in only -
              much higher quality but far slower/costlier, see UI tooltip)
    """

    low: str = "ministral-3b-2512"
    medium: str = "mistral-small-2506"
    high: str = "mistral-medium-2508"
    enabled: bool = False


@dataclass
class MistralConfig:
    model: str = "mistral-small-latest"
    max_tokens: int = 4096
    temperature: float = 0.7
    # Found live: after a tool result (e.g. web_search) is fed back in, the
    # model could get stuck repeating the same sentence verbatim hundreds of
    # times until max_tokens was exhausted - no frequency_penalty was set at
    # all, and the larger max_tokens (raised 1024->4096 for legitimately
    # verbose persona replies) gave a runaway repetition much more room to
    # run before hitting any ceiling. A modest penalty discourages exact
    # phrase repetition without meaningfully constraining normal variety.
    frequency_penalty: float = 0.4
    # Found live (2nd occurrence): frequency_penalty alone didn't stop a
    # short-cycle loop ("```html```<html></html>``` " repeated for hundreds
    # of tokens) after an unhelpful tool result, at temperature=0.0 (greedy
    # decoding has no randomness to escape a repetitive attractor once
    # started). presence_penalty is a flat penalty for ANY token already
    # used at all (unlike frequency_penalty, which scales with repeat
    # count) - the standard complementary pair for exactly this failure mode.
    presence_penalty: float = 0.4
    timeout: float = 60.0
    max_retries: int = 3
    base_delay: float = 1.0
    # 0.0 = automatische RPS-Ermittlung anhand des Modellnamens.
    # Ein positiver Wert überschreibt die automatische Zuordnung.
    rate_limit_rps: float = 0.0
    difficulty_tiers: MistralDifficultyTiers = field(default_factory=MistralDifficultyTiers)


@dataclass
class WinUIConfig:
    exe_path: str = ""
    backend_port: int = 50051
    backend_wait_seconds: int = 10


@dataclass
class UIConfig:
    backend: str = "winui"  # winui | pyside6-legacy
    autostart: bool = False
    start_minimized: bool = False
    show_tray: bool = True
    winui: WinUIConfig = field(default_factory=WinUIConfig)


@dataclass
class MemoryConfig:
    enabled: bool = True
    storage_dir: str = "~/.tarno/memory"
    conversation_id: str = "default"
    episode_max_age_days: int = 30  # Phase 35: Pruning-Schwellenwert für Episoden
    preference_min_confidence: float = 0.3  # Phase 35: Pruning-Schwellenwert für Preferences


@dataclass
class SecurityConfig:
    secrets_backend: str = "keyring"  # keyring | encrypted_file | env
    audit_log_retention_days: int = 365
    pii_redaction_enabled: bool = True
    encryption_enabled: bool = True


@dataclass
class TelemetryConfig:
    structured_logging: bool = True
    metrics_enabled: bool = True
    crash_reporting: bool = False  # opt-in
    log_level: str = "INFO"


@dataclass
class PluginsConfig:
    enabled: bool = True
    directories: list[str] = field(default_factory=lambda: ["~/.tarno/plugins"])
    auto_load: bool = True


@dataclass
class CommandExecutionConfig:
    enabled: bool = True
    timeout: float = 0.0  # 0 = auf Fertigstellung warten
    log_dir: str = "~/.tarno/logs"
    dry_run_default: bool = False
    autonomy_mode: str = "balanced"  # manual | balanced | plan | ultimate (see AutonomyMode)


@dataclass
class VoicePermissionsConfig:
    policy_file: str = "~/.tarno/voice_policy.yaml"
    default_durations: dict[str, int | None] = field(
        default_factory=lambda: {
            "voice_input_basic": None,
            "voice_recording": 300,
            "voice_external_output": 600,
            "voice_game_integration": 1800,
            "voice_communication": 600,
        }
    )


@dataclass
class AudioManagerConfig:
    echo_cooldown_ms: int = 2000
    echo_energy_threshold: float = 0.15
    refresh_interval_ms: int = 2000
    use_overlay_fallback: bool = True


@dataclass
class MinecraftVoiceConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 19999


@dataclass
class DiscordClientConfig:
    enabled: bool = False
    ptt_key: str | None = None
    virtual_cable: str | None = None


@dataclass
class ProactiveConfig:
    """Block 3: autonome Trigger-Engine (Beobachtungs-Loop + TRACES-Relevanzfilter)."""

    enabled: bool = False
    tick_seconds: float = 10.0
    score_threshold: int = 85  # nur bei Score > threshold wird TTS getriggert (Phase 27)
    source_cooldown_seconds: float = 300.0  # Debounce je Quelle gegen Sprach-Loops (Phase 30)

    # TimeCalendarObserver (Phase 22) - nutzt briefing.calendar_file/calendar_days.
    calendar_lookahead_minutes: int = 15

    # SystemObserver (Phase 23) - psutil-basiert. Bewusst ohne Docker-Container-
    # Inspektion (keine neue Abhängigkeit für dieses eine Feature).
    cpu_threshold_percent: float = 90.0
    ram_threshold_percent: float = 90.0
    disk_threshold_percent: float = 90.0

    # UserBehaviorObserver (Phase 24) + Anti-Ablenkungs-Exekutive (Phase 28).
    distraction_apps: list[str] = field(default_factory=lambda: [
        "youtube", "netflix", "twitch", "steam", "discord",
    ])
    distraction_minutes_before_action: float = 5.0
    close_distraction_window: bool = False  # Phase 28 scharfschalten (schließt Fenster autonom)

    # IdleCuriosityObserver (Phase 29).
    idle_minutes_for_curiosity: float = 15.0


@dataclass
class VisionConfig:
    """Block 7: Vision-Layer (permanente Kamera + autonome Bildreaktion).

    Bewusst deaktiviert per Default (wie proactive.enabled in Block 3) -
    Kamera-Dauererfassung + Cloud-Bildanalyse sind privacy-sensibel genug,
    dass ein expliziter Opt-in nötig ist, kein stillschweigendes Anschalten.
    """

    enabled: bool = False
    device_index: int = 0
    device_name: str = ""  # optional: Name oder Index-String fuer Kamera-Auswahl
    base_fps: float = 1.0  # Basis-Abtastrate bei Stillstand (Phase 61)
    motion_fps: float = 3.0  # Abtastrate während erkannter Bewegung (Phase 61/62)
    motion_threshold: float = 25.0  # mittlere Pixel-Differenz, ab der "Bewegung" gilt
    candidate_frames: int = 5  # Kandidaten-Frames pro Bewegungsfenster (Phase 63)
    downscale_max_edge: int = 720  # längste Kante nach Downscaling (720p fuer bessere Details)
    jpeg_quality: int = 85  # bessere Bildqualitaet bei noch akzeptabler Payload
    # Phase 65: "pixtral-large-latest" (der urspr. Plan) existiert nicht mehr -
    # Mistral hat Vision-Fähigkeit direkt in die Flaggschiff-Modelle integriert
    # (verifiziert 2026-07-19: small/medium/large-latest akzeptieren alle
    # image_url). mistral-large-latest gewählt für beste Bildqualitäts-
    # Einschätzung, da Vision-Calls selten/getriggert sind, nicht pro Chat-Turn.
    vision_model: str = "mistral-large-latest"
    source_cooldown_seconds: float = 300.0  # Debounce, wie ProactiveConfig
    score_threshold: int = 85  # eigener Schwellenwert, da Vision-Calls Geld kosten
    show_status_indicator: bool = True  # Phase 69


@dataclass
class MeshConfig:
    """Dynamic Hybrid Mesh: Handy-Hub/Handy-Zweitgeraet/ESP32 node aggregation
    + hub failover. Bewusst geraeteneutral gehalten (kein Marken-/Modellname
    im Code) - andere Nutzer haben andere Handymodelle als die, mit denen das
    hier urspruenglich entwickelt wurde.

    Bewusst deaktiviert per Default (wie proactive.enabled/vision.enabled) -
    öffnet einen UDP-Port und ggf. einen lokalen MQTT-Broker, das ist ein
    expliziter Opt-in, kein stillschweigendes Netzwerkverhalten."""

    enabled: bool = False
    udp_port: int = 47800
    mqtt_port: int = 1883
    hub_host: str | None = None
    # Die per Tasker/MacroDroid gesendeten UDP-Pakete tragen einen frei
    # waehlbaren sender_node-String (z.B. der Handymodellname) - diese beiden
    # Substrings entscheiden, welches der beiden Handys als Hub bzw. als
    # Zweitgeraet gilt (siehe router.py:_classify_sender). Konfigurierbar,
    # statt hart auf ein bestimmtes Modell verdrahtet zu sein - jeder Nutzer
    # traegt hier einfach ein, was SEINE beiden Handys broadcasten. Die
    # Defaults ("WIKO"/"ZTE") passen zur bereits laufenden Tasker-Konfiguration
    # dieser Installation - neue Nutzer ueberschreiben sie in ihrer eigenen
    # tarno_config.yaml mit den Namen, die ihre eigenen Handys broadcasten.
    hub_node_match: str = "WIKO"
    secondary_node_match: str = "ZTE"
    heartbeat_interval_seconds: float = 4.0
    score_threshold: int = 85  # eigener Schwellenwert, wie proactive/vision
    source_cooldown_seconds: float = 300.0  # Debounce, wie ProactiveConfig

    # Cloud-Tracking (tarno-server, siehe integrations/mesh/cloud_client.py) -
    # komplett getrennt vom lokalen UDP/MQTT-Hub oben, deshalb kein eigenes
    # enabled-Flag: der mesh_device_status-Tool-Call meldet einfach "kein
    # Login gefunden", wenn niemand in der Desktop-App eingeloggt ist, statt
    # eine zusaetzliche Konfigurationsoption zu verlangen.
    cloud_server_url: str = "https://tarno.cousinsmp.de"


@dataclass
class ContextEfficiencyConfig:
    """Chat-Umschalter "Kontext-Effizienz" (Beta) - siehe
    tarno/ai/context/ (output_compressor.py, usage_tracker.py,
    summarizer.py). Default aus, wie vision.enabled - neues,
    experimentelles Verhalten braucht einen expliziten Opt-in statt
    stillschweigend das bestehende Chat-Verhalten zu aendern."""

    enabled: bool = False


@dataclass
class OverlayConfig:
    enabled: bool = True
    position: str = "bottom_right"
    opacity: float = 0.85


@dataclass
class LLMConfig:
    provider: str = "mistral"  # "mistral" / "gemini" / "huggingface" / "groq" / "ollama" / "claude" / plus openai_compatible keys
    fallback_providers: list[str] = field(default_factory=list)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    groq: GroqConfig = field(default_factory=GroqConfig)
    huggingface: HuggingFaceConfig = field(default_factory=HuggingFaceConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    mistral: MistralConfig = field(default_factory=MistralConfig)
    openai_compatible: dict[str, OpenAICompatibleConfig] = field(default_factory=dict)
    max_history: int = 20
    max_coding_iterations: int = 0  # 0 = deaktiviert/unbegrenzt (Code begrenzt intern auf 10.000)


@dataclass
class CodingConfig:
    """Configuration for the autonomous coding-agent backend."""

    enabled: bool = True
    provider: str = "mistral"  # provider slug, see aider/litellm mapping
    # Codestral statt mistral-small-latest: dediziertes Coding-Modell, deutlich
    # kompetenter beim tatsächlichen Editieren als das kleine Allzweckmodell -
    # siehe native_agent.py-Docstring. Mit backend="native" ist dieser
    # Model-Name direkt der Mistral-API-Modellname (kein Aider/litellm-Präfix
    # mehr nötig); AiderBackend leitet ihn weiterhin über _PROVIDER_PREFIX
    # (aider_adapter.py) her, falls backend="aider" gewählt wird.
    model: str = "codestral-latest"
    # "native" (Standard): eigene Tool-Calling-Schleife, siehe native_agent.py.
    # "aider": alter Aider-CLI-Adapter (aider-chat muss installiert sein).
    backend: str = "native"
    read_only_default: bool = False
    timeout: float = 0.0  # 0.0 = kein Zeitlimit für Coding-Agent
    auto_allow: bool = False
    # Agent-Pool (Phase 0, reine Config - Orchestrator kommt in Phase 2):
    # begrenzt die Poolgroesse (UI-Auswahl) und wie oft der Lead Revisionen
    # von Workern anfordern darf, bevor er zwangsweise mergen muss - siehe
    # PoolOrchestrator, verhindert endlose Rueckfrage-Schleifen.
    pool_max_agents: int = 4
    pool_max_lead_iterations: int = 3
    # Maximale gleichzeitige HTTP-Anfragen PRO PROVIDER-NAME (nicht pro
    # Agent) - verhindert, dass mehrere Pool-Agenten desselben Providers
    # (z.B. 3 Mistral-Modelle) gleichzeitig feuern und dessen Rate-Limit
    # (HTTP 429) ausloesen. Siehe tarno/ai/factory.py get_provider_semaphore().
    pool_provider_max_concurrent: int = 2
    # Haertes Iterationslimit fuer die Tool-Calling-Schleife eines einzelnen
    # Pool-Workers (read_file) - verhindert Endlosschleifen, falls ein Modell
    # wiederholt Tools aufruft ohne je zu einer Textantwort zu kommen.
    pool_worker_max_tool_iterations: int = 4


@dataclass
class TarnoConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    wakeword: WakeWordConfig = field(default_factory=WakeWordConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    coding: CodingConfig = field(default_factory=CodingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    command_execution: CommandExecutionConfig = field(default_factory=CommandExecutionConfig)
    voice_permissions: VoicePermissionsConfig = field(default_factory=VoicePermissionsConfig)
    audio_manager: AudioManagerConfig = field(default_factory=AudioManagerConfig)
    minecraft_voice: MinecraftVoiceConfig = field(default_factory=MinecraftVoiceConfig)
    discord_client: DiscordClientConfig = field(default_factory=DiscordClientConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    agc: AGCConfig = field(default_factory=AGCConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    context_efficiency: ContextEfficiencyConfig = field(default_factory=ContextEfficiencyConfig)
    language: str = "de"
    theme: str = "dark"
    log_level: str = "INFO"

    def set_language(self, language: str) -> bool:
        """Switch UI and audio language. Returns True if the language was
        changed. This does not touch wake-word thresholds, microphone or any
        other audio settings - only the STT/TTS language and the default voice
        repository."""
        language = language.lower()
        if language not in _DEFAULT_TTS_VOICE:
            log.warning("Unbekannte Sprache: %s", language)
            return False
        if self.language == language and self.audio.language == language:
            return False
        self.language = language
        self.audio.language = language
        self.audio.voice = _DEFAULT_TTS_VOICE[language]

        tts_defaults = _TTS_PROMPT_LANGUAGE_DEFAULTS.get(language)
        if tts_defaults is not None:
            self.audio.tts_prompt.voice_hint = tts_defaults["voice_hint"]
            self.audio.tts_prompt.filler_words = list(tts_defaults["filler_words"])
            self.audio.tts_prompt.connective_phrases = list(tts_defaults["connective_phrases"])

        return True

    @classmethod
    def load(cls, path: Path | None = None) -> TarnoConfig:
        raw: dict[str, Any] = {}

        if _DEFAULT_CONFIG.exists():
            raw = _load_yaml(_DEFAULT_CONFIG)

        if path and path.exists():
            raw = _deep_merge(raw, _load_yaml(path))

        user_path = Path.home() / ".tarno" / "config" / _USER_CONFIG_NAME
        if user_path.exists():
            raw = _deep_merge(raw, _load_yaml(user_path))

        cwd_user_path = Path.cwd() / _USER_CONFIG_NAME
        if cwd_user_path.exists():
            raw = _deep_merge(raw, _load_yaml(cwd_user_path))

        raw = _apply_env_overrides(raw)

        return _dict_to_config(raw)

    def save(self, path: Path) -> None:
        """Atomically write config to *path*.

        Strategy:
        1. Write to a temporary file in the same directory.
        2. Backup existing config (if any) to ``path.bak``.
        3. Atomically replace the target via ``os.replace()``.

        A crash at any point leaves either the old or the new config intact.
        """
        import tempfile
        data = _config_to_dict(self)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first (same dir ensures same filesystem for rename)
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp", prefix=".tarno_cfg_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                f.flush()
                os.fsync(f.fileno())

            # Backup existing config
            if path.exists():
                backup = path.with_suffix(path.suffix + ".bak")
                try:
                    import shutil
                    shutil.copy2(str(path), str(backup))
                except Exception:
                    log.warning("Config-Backup konnte nicht erstellt werden: %s", backup)

            # Atomic replace
            os.replace(tmp_path, str(path))
            log.debug("Konfiguration atomar gespeichert: %s", path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file with automatic fallback to ``.bak`` on corruption."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
            # File is valid YAML but not a dict (e.g. null, list) — treat as corrupt
            log.warning("Konfiguration %s hat unerwartetes Format — versuche Backup", path)
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        log.error("Konfiguration %s ist beschädigt: %s — versuche Backup", path, exc)
    except OSError:
        return {}

    # Try backup
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        try:
            with open(backup, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    log.info("Backup-Konfiguration geladen: %s", backup)
                    return data
        except Exception:
            log.exception("Backup-Konfiguration %s ebenfalls beschädigt", backup)

    log.warning("Keine gültige Konfiguration gefunden — verwende Standardwerte")
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


_ENV_MAP = {
    "TARNO_LOG_LEVEL": "log_level",
    "TARNO_LANGUAGE": "language",
    "TARNO_THEME": "theme",
    "TARNO_LLM_PROVIDER": "llm.provider",
    "TARNO_LLM_FALLBACK_PROVIDERS": "llm.fallback_providers",
    "TARNO_CLAUDE_MODEL": "llm.claude.model",
    "TARNO_CLAUDE_MAX_TOKENS": "llm.claude.max_tokens",
    "TARNO_OLLAMA_MODEL": "llm.ollama.model",
    "TARNO_OLLAMA_URL": "llm.ollama.base_url",
    "TARNO_GROQ_MODEL": "llm.groq.model",
    "TARNO_HF_MODEL": "llm.huggingface.model",
    "TARNO_GEMINI_MODEL": "llm.gemini.model",
    "TARNO_MISTRAL_MODEL": "llm.mistral.model",
    "TARNO_WAKEWORD_ENABLED": "wakeword.enabled",
    "TARNO_WAKEWORD_THRESHOLD": "wakeword.threshold",
    "TARNO_WAKEWORD_SENSITIVITY": "wakeword.sensitivity",
    "TARNO_WAKEWORD_MICROPHONE": "audio.microphone_device",
    "TARNO_TTS_ENGINE": "audio.tts_engine",
    "TARNO_BRIEFING_ENABLED": "briefing.enabled",
    "TARNO_BRIEFING_TRIGGER_ON_START": "briefing.trigger_on_start",
}


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    for env_key, config_path in _ENV_MAP.items():
        value = os.environ.get(env_key)
        if value is None:
            continue

        parts = config_path.split(".")
        target = raw
        for part in parts[:-1]:
            target = target.setdefault(part, {})

        leaf = parts[-1]
        if value.lower() in ("true", "false"):
            target[leaf] = value.lower() == "true"
        elif value.isdigit():
            target[leaf] = int(value)
        else:
            try:
                target[leaf] = float(value)
            except ValueError:
                target[leaf] = value

    return raw


def _dict_to_config(raw: dict[str, Any]) -> TarnoConfig:
    audio_raw = raw.get("audio", {})
    wakeword_raw = raw.get("wakeword", {})
    briefing_raw = raw.get("briefing", {})
    llm_raw = raw.get("llm", {})
    claude_raw = llm_raw.get("claude", raw.get("claude", {}))
    ollama_raw = llm_raw.get("ollama", {})
    groq_raw = llm_raw.get("groq", {})
    hf_raw = llm_raw.get("huggingface", {})
    gemini_raw = llm_raw.get("gemini", {})
    mistral_raw = dict(llm_raw.get("mistral", {}))
    tiers_raw = mistral_raw.pop("difficulty_tiers", None)
    if isinstance(tiers_raw, dict):
        mistral_raw["difficulty_tiers"] = MistralDifficultyTiers(
            **{k: v for k, v in tiers_raw.items() if k in MistralDifficultyTiers.__dataclass_fields__}
        )

    fallback = llm_raw.get("fallback_providers", [])
    if isinstance(fallback, str):
        fallback = [p.strip() for p in fallback.split(",") if p.strip()]

    compat_raw = llm_raw.get("openai_compatible", {})
    if not isinstance(compat_raw, dict):
        compat_raw = {}
    openai_compatible: dict[str, OpenAICompatibleConfig] = {}
    for key, item in compat_raw.items():
        if not isinstance(item, dict):
            continue
        openai_compatible[key] = OpenAICompatibleConfig(
            **{k: v for k, v in item.items() if k in OpenAICompatibleConfig.__dataclass_fields__}
        )

    llm_config = LLMConfig(
        provider=llm_raw.get("provider", "mistral"),
        fallback_providers=fallback,
        claude=ClaudeConfig(**{k: v for k, v in claude_raw.items() if k in ClaudeConfig.__dataclass_fields__}),
        ollama=OllamaConfig(**{k: v for k, v in ollama_raw.items() if k in OllamaConfig.__dataclass_fields__}),
        groq=GroqConfig(**{k: v for k, v in groq_raw.items() if k in GroqConfig.__dataclass_fields__}),
        huggingface=HuggingFaceConfig(**{k: v for k, v in hf_raw.items() if k in HuggingFaceConfig.__dataclass_fields__}),
        gemini=GeminiConfig(**{k: v for k, v in gemini_raw.items() if k in GeminiConfig.__dataclass_fields__}),
        mistral=MistralConfig(**{k: v for k, v in mistral_raw.items() if k in MistralConfig.__dataclass_fields__}),
        openai_compatible=openai_compatible,
        max_history=llm_raw.get("max_history", 20),
        max_coding_iterations=llm_raw.get("max_coding_iterations", 0),
    )

    def _section(name: str, cls: type) -> Any:
        section_raw = raw.get(name, {})
        return cls(**{k: v for k, v in section_raw.items() if k in cls.__dataclass_fields__})

    ui_raw = raw.get("ui", {})
    winui_raw = ui_raw.get("winui", {})
    ui_config = UIConfig(
        backend=ui_raw.get("backend", "winui"),
        autostart=ui_raw.get("autostart", False),
        start_minimized=ui_raw.get("start_minimized", False),
        show_tray=ui_raw.get("show_tray", True),
        winui=WinUIConfig(**{k: v for k, v in winui_raw.items() if k in WinUIConfig.__dataclass_fields__}),
    )

    tts_prompt_raw = audio_raw.get("tts_prompt")
    if isinstance(tts_prompt_raw, dict):
        audio_raw["tts_prompt"] = TTSPromptConfig(
            **{k: v for k, v in tts_prompt_raw.items() if k in TTSPromptConfig.__dataclass_fields__}
        )

    return TarnoConfig(
        audio=AudioConfig(**{k: v for k, v in audio_raw.items() if k in AudioConfig.__dataclass_fields__}),
        wakeword=WakeWordConfig(**{k: v for k, v in wakeword_raw.items() if k in WakeWordConfig.__dataclass_fields__}),
        briefing=BriefingConfig(**{k: v for k, v in briefing_raw.items() if k in BriefingConfig.__dataclass_fields__}),
        llm=llm_config,
        ui=ui_config,
        # KERNFIX (Code-Review): fehlte komplett - die gesamte "coding:"-
        # YAML-Sektion (default.yaml UND jede Nutzer-Override-Datei) wurde
        # dadurch nie angewendet, TarnoConfig griff hier immer stillschweigend
        # auf die CodingConfig()-Python-Defaults zurück, unabhängig davon, was
        # in der Config-Datei stand. Live bestätigt: default.yaml setzt
        # coding.model auf "mistral-small-latest", TarnoConfig.load().coding.model
        # lieferte trotzdem den Dataclass-Default. Betraf auch auto_allow,
        # read_only_default, timeout, backend und alle pool_*-Felder.
        coding=_section("coding", CodingConfig),
        security=_section("security", SecurityConfig),
        telemetry=_section("telemetry", TelemetryConfig),
        plugins=_section("plugins", PluginsConfig),
        command_execution=_section("command_execution", CommandExecutionConfig),
        voice_permissions=_section("voice_permissions", VoicePermissionsConfig),
        audio_manager=_section("audio_manager", AudioManagerConfig),
        minecraft_voice=_section("minecraft_voice", MinecraftVoiceConfig),
        discord_client=_section("discord_client", DiscordClientConfig),
        overlay=_section("overlay", OverlayConfig),
        vad=_section("vad", VADConfig),
        agc=_section("agc", AGCConfig),
        proactive=_section("proactive", ProactiveConfig),
        vision=_section("vision", VisionConfig),
        mesh=_section("mesh", MeshConfig),
        language=raw.get("language", "de"),
        theme=raw.get("theme", "dark"),
        log_level=raw.get("log_level", "INFO"),
    )


def _config_to_dict(config: TarnoConfig) -> dict[str, Any]:
    from dataclasses import asdict
    return asdict(config)
