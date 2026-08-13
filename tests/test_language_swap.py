"""Tests for the full-stack language swap feature (de | en)."""

from __future__ import annotations

import pytest

from tarno.core.config import AudioConfig, TarnoConfig


def test_set_language_updates_tarno_config_and_audio():
    config = TarnoConfig(audio=AudioConfig())
    assert config.language == "de"
    assert config.audio.language == "de"
    assert config.audio.voice == "Trelis/piper-de-de-thorsten-medium"

    changed = config.set_language("en")
    assert changed is True
    assert config.language == "en"
    assert config.audio.language == "en"
    assert config.audio.voice == "Trelis/piper-en-us-ryan-medium"


def test_set_language_returns_false_when_already_active():
    config = TarnoConfig(audio=AudioConfig())
    config.set_language("en")
    changed = config.set_language("en")
    assert changed is False


def test_set_language_rejects_unknown_language():
    config = TarnoConfig(audio=AudioConfig())
    changed = config.set_language("fr")
    assert changed is False
    assert config.language == "de"
