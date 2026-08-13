"""TTS-specific prompt generation for the Thorsten/Piper voice."""

from __future__ import annotations

from tarno_backend.core.config import TTSPromptConfig


def build_tts_prompt(cfg: TTSPromptConfig) -> str:
    """Return a Thorsten-optimized TTS instruction block for the system prompt.

    The returned text is written in German and uses the configured voice hint,
    filler words and connective phrases. It is appended to the chat system prompt
    so the LLM produces spoken-style sentences, avoids rigid lists and uses
    punctuation for intonation.
    """
    if not cfg.enabled:
        return ""

    voice_name = "Thorsten" if cfg.voice_hint == "thorsten" else "lokalen Stimme"
    fillers = ", ".join(f'"{w}"' for w in cfg.filler_words[:8])
    connectors = ", ".join(f'"{w}"' for w in cfg.connective_phrases[:5])

    return f"""\
Deine Antworten werden von Piper mit der deutschen {voice_name}-Stimme vorgelesen. \
Optimiere daher den gesamten Text für gesprochenes Deutsch und folgende Sprechregeln:

- Satzbau: Zerlege lange Schachtelsätze in kurze, eigenständige Sätze. Ein Satz sollte \
  idealerweise nicht mehr als {cfg.max_sentence_words} Wörter enthalten, damit Thorsten \
  natürliche Atempausen setzt.
- Verbindungen statt Aufzählungen: Wenn du mehrere Punkte nennen musst, verbinde sie \
  flüssig mit Wendungen wie {connectors}. Vermeide stures \"Erstens..., Zweitens...\", \
  nummerierte Listen oder starre Aufzählungszeichen.
- Füller und Intonation: Du darfst natürliche Füller wie {fillers} sparsam einstreuen \
  und Pausen mit \"...\" setzen, um Thorsten Ansatzpunkte für Pausen und Tonhöhenwechsel zu geben. \
  Fülle aber nicht jeden Satz.
- Satzzeichen bewusst setzen: Verwende Ausrufezeichen (!) und Fragezeichen (?), damit Thorsten \
  die Satzendmelodie nach oben oder unten zieht. Vermeide Klammern, Schrägstriche, Sterne, \
  Doppelpunkt-Listen und andere Zeichen, die Buchstabe für Buchstabe vorgelesen werden könnten.
- Kein Markdown, keine Tabellen, keine URLs, keine Code-Blöcke und keine Aufzählungslisten.
"""
