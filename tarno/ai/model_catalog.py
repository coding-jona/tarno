"""Curated per-provider model catalog for the WinUI model picker (Phase 1-6).

Each provider exposes a short, hand-picked list of models (not the full
catalog the provider's API offers) - free-tier/generous models only, with a
human-readable rate-limit note and 1-3 capability keywords so the user can
tell at a glance which model fits their current task. Numbers are research
snapshots (2026-07-20 via official docs/pricing pages) and will drift as
providers change their free tiers - re-verify before relying on them for
anything precise.

Ollama is intentionally NOT listed here: it has no fixed model set (whatever
the user has pulled locally) and no cloud rate limit - see
TarnoEngine.list_ollama_models, which queries the local Ollama server
directly instead of a static catalog.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    rate_limit_note: str
    capabilities: tuple[str, ...]


MISTRAL_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="codestral-latest",
        label="Codestral Latest",
        rate_limit_note="kostenlos · 1.500/Tag · coding-optimiert",
        capabilities=("coding", "langer Kontext", "FIM"),
    ),
    ModelInfo(
        id="mistral-large-latest",
        label="Mistral Large Latest",
        rate_limit_note="kostenlos · 1.500/Tag · stärkstes Modell",
        capabilities=("reasoning", "Tool-Calls", "komplex"),
    ),
    ModelInfo(
        id="mistral-medium-latest",
        label="Mistral Medium Latest",
        rate_limit_note="kostenlos · 1.500/Tag · ausgewogen",
        capabilities=("ausgewogen", "schnell", "allgemein"),
    ),
    ModelInfo(
        id="mistral-small-latest",
        label="Mistral Small Latest",
        rate_limit_note="kostenlos · 1.500/Tag · sehr schnell",
        capabilities=("schnell", "günstig", "einfache Aufgaben"),
    ),
    ModelInfo(
        id="ministral-3b-latest",
        label="Ministral 3B Latest",
        rate_limit_note="kostenlos · 1.500/Tag · Edge / schnell",
        capabilities=("schnell", "leicht", "lokale Edge"),
    ),
    ModelInfo(
        id="pixtral-large-latest",
        label="Pixtral Large Latest",
        rate_limit_note="kostenlos · 1.500/Tag · multimodal (Bilder)",
        capabilities=("vision", "multimodal", "Bildanalyse"),
    ),
)

CLAUDE_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="claude-haiku-4-5-20251001",
        label="Claude Haiku 4.5",
        rate_limit_note="$5 einmalig, danach kostenpflichtig · Tier 1 ~50/Min",
        capabilities=("schnell", "günstig", "lange Kontexte"),
    ),
    ModelInfo(
        id="claude-sonnet-5",
        label="Claude Sonnet 5",
        rate_limit_note="$5 einmalig, danach kostenpflichtig · Tier 1 ~50/Min",
        capabilities=("ausgewogen", "starkes Reasoning", "Tool-Calls"),
    ),
)

GEMINI_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        rate_limit_note="kostenlos · ca. 10-15/Min · 1.500/Tag",
        capabilities=("schnell", "1M Kontext", "multimodal"),
    ),
    ModelInfo(
        id="gemini-2.5-flash-lite",
        label="Gemini 2.5 Flash-Lite",
        rate_limit_note="kostenlos · ca. 10-15/Min · 1.500/Tag",
        capabilities=("am günstigsten", "hohe Frequenz", "Datenextraktion"),
    ),
)

GROQ_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="llama-3.3-70b-versatile",
        label="Llama 3.3 70B Versatile",
        rate_limit_note="kostenlos · 30/Min · 1.000/Tag · 12.000 TPM",
        capabilities=("vielseitig", "Tool-Calls", "70B-Qualität"),
    ),
    ModelInfo(
        id="gemma2-9b-it",
        label="Gemma 2 9B",
        rate_limit_note="kostenlos · 30/Min · 1.000/Tag · 15.000 TPM",
        capabilities=("sehr schnell", "höheres TPM-Kontingent", "leichte Aufgaben"),
    ),
)

HUGGINGFACE_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct",
        label="Llama 3.1 8B Instruct",
        rate_limit_note="kostenlos · einige hundert Anfragen/Std (nicht fix dokumentiert)",
        capabilities=("bewährt", "vielseitig", "8B, unter Free-Tier-Grenze"),
    ),
    ModelInfo(
        id="microsoft/Phi-4-mini-instruct",
        label="Phi-4-mini Instruct",
        rate_limit_note="kostenlos · einige hundert Anfragen/Std (nicht fix dokumentiert)",
        capabilities=("ressourcenschonend", "gutes Reasoning", "klein"),
    ),
)

OPENAI_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="gpt-4o-mini",
        label="GPT-4o mini",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("schnell", "günstig", "allgemein"),
    ),
    ModelInfo(
        id="gpt-4o",
        label="GPT-4o",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("stark", "multimodal", "Tool-Calls"),
    ),
    ModelInfo(
        id="o3-mini",
        label="o3-mini",
        rate_limit_note="Limits tier-abhängig · 200k Kontext",
        capabilities=("Reasoning", "Coding", "mathematisch"),
    ),
    ModelInfo(
        id="gpt-4-turbo",
        label="GPT-4 Turbo",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("ausgewogen", "langer Kontext", "Tool-Calls"),
    ),
)

GLM_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="glm-4.7-flash",
        label="GLM-4.7 Flash",
        rate_limit_note="Limits tier-abhängig · 200k Kontext",
        capabilities=("schnell", "günstig", "Coding"),
    ),
    ModelInfo(
        id="glm-4.7-air",
        label="GLM-4.7 Air",
        rate_limit_note="Limits tier-abhängig · 200k Kontext",
        capabilities=("ausgewogen", "Alltag", "lang"),
    ),
    ModelInfo(
        id="glm-4.7-plus",
        label="GLM-4.7 Plus",
        rate_limit_note="Limits tier-abhängig · 200k Kontext",
        capabilities=("stark", "Reasoning", "Komplexes"),
    ),
)

PERPLEXITY_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="sonar",
        label="Sonar",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("günstig", "Web-Suche", "Schnell"),
    ),
    ModelInfo(
        id="sonar-pro",
        label="Sonar Pro",
        rate_limit_note="Limits tier-abhängig · 200k Kontext",
        capabilities=("tiefere Suche", "Zitationen", "Forschung"),
    ),
    ModelInfo(
        id="sonar-reasoning",
        label="Sonar Reasoning",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("Reasoning", "Chain-of-Thought", "Suche"),
    ),
    ModelInfo(
        id="sonar-deep-research",
        label="Sonar Deep Research",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("tiefgehend", "Recherche", "Zitationen"),
    ),
)

META_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="llama-3.3-70b-instruct",
        label="Llama 3.3 70B Instruct",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("open", "ausgewogen", "Tool-Calls"),
    ),
    ModelInfo(
        id="llama-3.2-90b-vision-instruct",
        label="Llama 3.2 90B Vision",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("Vision", "Bilder", "multimodal"),
    ),
    ModelInfo(
        id="llama-3.1-405b-instruct",
        label="Llama 3.1 405B Instruct",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("maximale Qualität", "langsamer", "Reasoning"),
    ),
)

DEEPSEEK_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="deepseek-v4-flash",
        label="DeepSeek-V4 Flash",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("schnell", "günstig", "Coding"),
    ),
    ModelInfo(
        id="deepseek-chat",
        label="DeepSeek Chat",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("ausgewogen", "langer Kontext", "Allgemein"),
    ),
    ModelInfo(
        id="deepseek-coder",
        label="DeepSeek Coder",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("Coding", "FIM", "Software"),
    ),
    ModelInfo(
        id="deepseek-reasoner",
        label="DeepSeek Reasoner",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("Reasoning", "Mathematik", "stark"),
    ),
)

MOONSHOT_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="kimi-k3",
        label="Kimi K3",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("lang", "Reasoning", "Coding"),
    ),
    ModelInfo(
        id="moonshot-v1-128k",
        label="Moonshot v1 128k",
        rate_limit_note="Limits tier-abhängig · 128k Kontext",
        capabilities=("langer Kontext", "Dokumente", "schnell"),
    ),
    ModelInfo(
        id="moonshot-v1-32k",
        label="Moonshot v1 32k",
        rate_limit_note="Limits tier-abhängig · 32k Kontext",
        capabilities=("ausgewogen", "kürzer", "günstig"),
    ),
    ModelInfo(
        id="moonshot-v1-8k",
        label="Moonshot v1 8k",
        rate_limit_note="Limits tier-abhängig · 8k Kontext",
        capabilities=("günstig", "schnell", "simple Aufgaben"),
    ),
)

QWEN_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="qwen3.7-plus",
        label="Qwen 3.7 Plus",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("stark", "Coding", "multilingual"),
    ),
    ModelInfo(
        id="qwen-max",
        label="Qwen Max",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("Spitzenleistung", "Reasoning", "komplex"),
    ),
    ModelInfo(
        id="qwen-plus",
        label="Qwen Plus",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("ausgewogen", "schnell", "allgemein"),
    ),
    ModelInfo(
        id="qwen-coder-plus",
        label="Qwen Coder Plus",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("Coding", "Code-Generierung", "Software"),
    ),
    ModelInfo(
        id="qwen-turbo",
        label="Qwen Turbo",
        rate_limit_note="Limits tier-abhängig · 1M Kontext",
        capabilities=("günstig", "sehr schnell", "einfach"),
    ),
)

OPENROUTER_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="openai/gpt-4o-mini",
        label="OpenAI GPT-4o mini",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 128k Kontext",
        capabilities=("günstig", "schnell", "OpenAI"),
    ),
    ModelInfo(
        id="openai/gpt-4o",
        label="OpenAI GPT-4o",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 128k Kontext",
        capabilities=("stark", "multimodal", "OpenAI"),
    ),
    ModelInfo(
        id="anthropic/claude-sonnet-5",
        label="Anthropic Claude Sonnet 5",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 200k Kontext",
        capabilities=("Reasoning", "Coding", "Claude"),
    ),
    ModelInfo(
        id="google/gemini-3.5-flash",
        label="Google Gemini 3.5 Flash",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 1M Kontext",
        capabilities=("schnell", "multimodal", "Google"),
    ),
    ModelInfo(
        id="meta-llama/llama-3.3-70b-instruct",
        label="Meta Llama 3.3 70B",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 128k Kontext",
        capabilities=("offen", "ausgewogen", "Meta"),
    ),
    ModelInfo(
        id="deepseek/deepseek-v4-flash",
        label="DeepSeek V4 Flash",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 1M Kontext",
        capabilities=("günstig", "Coding", "DeepSeek"),
    ),
    ModelInfo(
        id="qwen/qwen3.7-plus",
        label="Qwen 3.7 Plus",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 1M Kontext",
        capabilities=("stark", "Coding", "Qwen"),
    ),
    ModelInfo(
        id="moonshotai/kimi-k3",
        label="Moonshot Kimi K3",
        rate_limit_note="kostenpflichtig + Routing-Gebühr · 1M Kontext",
        capabilities=("lang", "Reasoning", "Moonshot"),
    ),
)

PROVIDER_MODEL_CATALOG: dict[str, tuple[ModelInfo, ...]] = {
    "mistral": MISTRAL_MODELS,
    "claude": CLAUDE_MODELS,
    "gemini": GEMINI_MODELS,
    "groq": GROQ_MODELS,
    "huggingface": HUGGINGFACE_MODELS,
    "openai": OPENAI_MODELS,
    "glm": GLM_MODELS,
    "perplexity": PERPLEXITY_MODELS,
    "meta": META_MODELS,
    "deepseek": DEEPSEEK_MODELS,
    "moonshot": MOONSHOT_MODELS,
    "qwen": QWEN_MODELS,
    "openrouter": OPENROUTER_MODELS,
}
