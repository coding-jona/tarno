"""Zero-Trust content filter for TARNO's LLM pipeline.

Defense-in-depth layer 2 (after the system-prompt hardening in
``tarno/ai/conversation.py``): a lexical gate that inspects both LLM *input*
(user text before it is sent to the model) and LLM *output* (generated code
before it is displayed or executed).

Born out of the "Great TARNO Overload Incident" (2026-07-15): a batch script
combining ``goto loop`` with ``start`` spawned 3311 processes and exhausted
system RAM. The existing ``CommandEngine`` blocklist did NOT cover that
fork-bomb / infinite-loop-with-spawn class, so this filter closes that gap and
adds an input-side gate on top.

This is the Python counterpart of the Android/Kotlin ``CodeSafetyScanner`` and
keeps the exact same detection logic for cross-platform parity.

ReDoS note (honest, cross-language): unlike .NET's ``Regex`` there is NO native
per-match timeout in Python's stdlib ``re``. The defense here is therefore
*structural*: every pattern is linear and anchored with no nested/ambiguous
quantifiers, so catastrophic backtracking is impossible by construction. A hard
wall-clock cap (via the third-party ``regex`` package's ``timeout=`` argument or
a watchdog thread) can be layered on later if ever required, but is not needed
for these patterns.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)

_MAX_BASE64_RECURSION_DEPTH = 3
_MIN_BASE64_RUN = 40


class Verdict(Enum):
    SAFE = "safe"
    BLOCKED = "blocked"
    WARNING = "warning"


@dataclass(frozen=True)
class ScanResult:
    verdict: Verdict
    reason: str | None = None


# Homoglyph map: a handful of the most common Cyrillic/Greek lookalikes that get
# abused to smuggle keywords past a naive latin-only filter. Not exhaustive by
# design - just the letters that appear in the command keywords we care about.
_HOMOGLYPHS = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "к": "k", "м": "m", "т": "t", "н": "h", "в": "b", "і": "i", "ѕ": "s",
    "ο": "o", "ε": "e", "α": "a", "ρ": "p", "τ": "t", "ν": "v", "κ": "k",
}


def _strip_invisibles(text: str) -> str:
    """Drop control chars, zero-width spaces and bidi/format markers."""
    result = []
    for ch in text:
        if ch in ("\n", "\t", "\r", " "):
            result.append(ch)
            continue
        category = unicodedata.category(ch)
        # Cc = control, Cf = format (zero-width, RTL/LTR marks, etc.).
        if category in ("Cc", "Cf"):
            continue
        result.append(ch)
    return "".join(result)


def _map_homoglyphs(text: str) -> str:
    return "".join(_HOMOGLYPHS.get(ch, ch) for ch in text)


def normalize(text: str) -> str:
    """Normalization pipeline: NFKC, homoglyph mapping, invisible stripping, lowercase."""
    text = unicodedata.normalize("NFKC", text)
    text = _map_homoglyphs(text)
    text = _strip_invisibles(text)
    return text.lower()


def _deobfuscate(text: str) -> str:
    """Collapse separator-based obfuscation ("p o w e r s h e l l", "c.m.d",
    "r_e_g_ _d_e_l_e_t_e") into a compact copy for a secondary scan. Removing
    whitespace/dots/underscores/hyphens is safe here because we only match this
    copy against keyword signatures, never display or execute it."""
    return re.sub(r"[\s._\-]+", "", text)


# --- Input-side blocklist (linear, anchored, IGNORECASE). ---
_INPUT_BLOCKLIST: list[tuple[re.Pattern[str], str]] = [
    # \s* (not \s+) and no trailing \b so the de-obfuscated compact form
    # ("regdelete", "formatc:") matches the same pattern as the spaced form.
    (re.compile(r"format\s*[a-z]:"), "Datenträger-Formatierung (format <Laufwerk>:)"),
    (re.compile(r"\breg\s*delete"), "Registry-Löschung (reg delete)"),
    (re.compile(r"\bshutdown\b"), "System-Herunterfahren (shutdown)"),
    (re.compile(r"\btaskkill\b"), "Prozess-Abschuss (taskkill)"),
    (re.compile(r"-executionpolicy\s+bypass"), "PowerShell-ExecutionPolicy-Bypass"),
    (re.compile(r"-ep\s+bypass"), "PowerShell-ExecutionPolicy-Bypass (-ep)"),
    (re.compile(r"(?:\s|^)-nop(?:rofile)?\b"), "PowerShell -NoProfile (Bypass-Indikator)"),
    (re.compile(r"-windowstyle\s+hidden"), "Verstecktes PowerShell-Fenster (-WindowStyle Hidden)"),
    (re.compile(r"-enc(?:odedcommand)?\s"), "Base64-kodierter PowerShell-Befehl (-EncodedCommand)"),
    (re.compile(r"\brunas\b"), "Rechteausweitung (runas)"),
    (re.compile(r"-verb\s+runas"), "Rechteausweitung (Start-Process -Verb RunAs)"),
    (re.compile(r"\bmimikatz\b"), "Credential-Diebstahl (mimikatz)"),
    (re.compile(r"\bsekurlsa\b"), "Credential-Diebstahl (sekurlsa)"),
    (re.compile(r"invoke-expression|\biex\b"), "Reflektierende Codeausführung (Invoke-Expression/iex)"),
    (re.compile(r"'\s*or\s*'1'\s*=\s*'1"), "SQL-Injection ('OR '1'='1)"),
    (re.compile(r"\bunion\s*select"), "SQL-Injection (UNION SELECT)"),
    (re.compile(r"\bor\s+1\s*=\s*1\b"), "SQL-Injection (OR 1=1)"),
    (re.compile(r"/dev/tcp/"), "Reverse-Shell (/dev/tcp/)"),
    (re.compile(r"\bnc\s+-e\b"), "Reverse-Shell (netcat -e)"),
    (re.compile(r"bash\s+-i\s+>?&"), "Reverse-Shell (bash -i)"),
]

# --- Prompt-injection signatures (linear, anchored, IGNORECASE). Distinct from
# _INPUT_BLOCKLIST above: that list targets dangerous *commands*, this one
# targets attempts to override TARNO's instructions/identity via user text. ---
_PROMPT_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"),
     "Instruktions-Überschreibung (ignore previous instructions)"),
    (re.compile(r"disregard\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:rules|instructions)"),
     "Instruktions-Überschreibung (disregard your rules)"),
    (re.compile(r"forget\s+(?:everything\s+)?(?:you\s+)?(?:were\s+)?told"),
     "Instruktions-Überschreibung (forget everything you were told)"),
    (re.compile(r"you\s+are\s+now\s+(?:a|an|in)\b"), "Identitäts-Override (you are now a/an...)"),
    (re.compile(r"new\s+system\s+prompt"), "Systemprompt-Override (new system prompt)"),
    (re.compile(r"act\s+as\s+(?:dan\b|jailbreak)"), "Bekanntes Jailbreak-Muster (DAN/jailbreak)"),
    (re.compile(r"\bdo\s+anything\s+now\b"), "Bekanntes Jailbreak-Muster (DAN: do anything now)"),
    (re.compile(r"pretend\s+(?:you\s+have\s+no|there\s+are\s+no)\s+(?:restrictions|rules|filters)"),
     "Identitäts-Override (pretend you have no restrictions)"),
    (re.compile(r"reveal\s+(?:your\s+)?system\s+prompt"), "Systemprompt-Exfiltration (reveal system prompt)"),
    (re.compile(r"du\s+bist\s+jetzt\s+(?:ein|eine|kein)\b"), "Identitäts-Override (du bist jetzt ein/eine...)"),
    (re.compile(r"ignoriere\s+(?:alle\s+)?(?:vorherigen|bisherigen)\s+anweisungen"),
     "Instruktions-Überschreibung (ignoriere vorherige Anweisungen)"),
    (re.compile(r"vergiss\s+(?:alles,?\s+)?was\s+(?:du\s+)?(?:zuvor\s+)?(?:gesagt|angewiesen)"),
     "Instruktions-Überschreibung (vergiss was du zuvor gesagt bekamst)"),
]

# --- Output-side hard signatures: known fork bombs / unclosable-window tricks. ---
_HARD_SIGNATURES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"%0\s*\|\s*%0"), "Batch-Fork-Bombe (%0|%0)"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "Bash-Fork-Bombe (:(){ :|:& };:)"),
    (re.compile(r"setwindowlong\w*\s*\([^)]*,\s*-26\s*,\s*-1", re.IGNORECASE),
     "Fenster-Schließen-Button deaktiviert (GWL_EXSTYLE -26) - der Trick aus dem Overload-Vorfall"),
    (re.compile(r"enablemenuitem\s*\([^)]*sc_close", re.IGNORECASE),
     "Fenster-Schließen-Menüeintrag deaktiviert"),
    (re.compile(r"\bws_disabled\b", re.IGNORECASE), "Fenster per WS_DISABLED unbedienbar gemacht"),
    (re.compile(r"\bping\s+-t\b", re.IGNORECASE), "Nicht-terminierender Ping (ping -t)"),
]

# --- Output-side heuristic building blocks (loop + spawn without breakout). ---
_INFINITE_LOOP_OPENERS: list[re.Pattern[str]] = [
    re.compile(r"(?m)^\s*:loop\b", re.IGNORECASE),   # Batch label
    re.compile(r"while\s*\(\s*true\s*\)", re.IGNORECASE),  # C/Kotlin/Java/PowerShell/JS
    re.compile(r"while\s*\(\s*\$true\s*\)", re.IGNORECASE),  # PowerShell
    re.compile(r"while\s+true\s*:"),                  # Python
    re.compile(r"for\s*\(\s*;;\s*\)"),                # C/C#/Java
]

_SPAWN_CALLS: list[re.Pattern[str]] = [
    re.compile(r"\bstart\s+.*?\.exe", re.IGNORECASE),          # Batch "start", incl. empty-title form
    re.compile(r"start-process\b", re.IGNORECASE),            # PowerShell
    re.compile(r"subprocess\.(?:popen|call|run)\b", re.IGNORECASE),  # Python
    re.compile(r"os\.(?:system|startfile|fork)\b", re.IGNORECASE),   # Python
    re.compile(r"processbuilder\s*\(", re.IGNORECASE),        # Java/Kotlin
    re.compile(r"runtime\.getruntime\(\)\.exec\b", re.IGNORECASE),   # Java/Kotlin
    re.compile(r"createwindowex?w?\s*\(", re.IGNORECASE),     # WinAPI window creation
    re.compile(r"new-object\s+-comobject\s+wscript\.shell", re.IGNORECASE),
]

_BREAK_INDICATORS: list[re.Pattern[str]] = [
    re.compile(r"\bbreak\b", re.IGNORECASE),
    re.compile(r"\breturn\b", re.IGNORECASE),
    re.compile(r"\bexit\b", re.IGNORECASE),
    re.compile(r"goto\s+:eof", re.IGNORECASE),
    re.compile(r"max(?:imum)?[_-]?(?:count|iterations|tries|attempts)\b", re.IGNORECASE),
]

_CODE_BLOCK_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)
_BASE64_RUN_RE = re.compile(rf"[A-Za-z0-9+/]{{{_MIN_BASE64_RUN},}}={{0,2}}")


class TarnoSecurity:
    """Lexical input/output gate for the LLM pipeline."""

    def scan_input(self, text: str, _depth: int = 0) -> ScanResult:
        """Check user text before it is sent to the LLM."""
        norm = normalize(text)
        variants = (norm, _deobfuscate(norm))

        for variant in variants:
            for pattern, reason in _INPUT_BLOCKLIST:
                if pattern.search(variant):
                    return ScanResult(Verdict.BLOCKED, reason)

        # Recursively unpack base64 payloads (depth-limited against StackOverflow).
        if _depth < _MAX_BASE64_RECURSION_DEPTH:
            for decoded in self._decode_base64_runs(text):
                nested = self.scan_input(decoded, _depth + 1)
                if nested.verdict != Verdict.SAFE:
                    return ScanResult(
                        nested.verdict,
                        f"In Base64 verstecktes Muster: {nested.reason}",
                    )

        return ScanResult(Verdict.SAFE)

    def scan_prompt_injection(self, text: str, _depth: int = 0) -> ScanResult:
        """Check user text for attempts to override TARNO's instructions/identity."""
        norm = normalize(text)
        variants = (norm, _deobfuscate(norm))

        for variant in variants:
            for pattern, reason in _PROMPT_INJECTION_PATTERNS:
                if pattern.search(variant):
                    return ScanResult(Verdict.BLOCKED, reason)

        if _depth < _MAX_BASE64_RECURSION_DEPTH:
            for decoded in self._decode_base64_runs(text):
                nested = self.scan_prompt_injection(decoded, _depth + 1)
                if nested.verdict != Verdict.SAFE:
                    return ScanResult(
                        nested.verdict,
                        f"In Base64 verstecktes Muster: {nested.reason}",
                    )

        return ScanResult(Verdict.SAFE)

    def scan_output(self, code: str, _depth: int = 0) -> ScanResult:
        """Check LLM-generated code before display or execution."""
        norm = normalize(code)

        for pattern, reason in _HARD_SIGNATURES:
            if pattern.search(norm):
                return ScanResult(Verdict.BLOCKED, reason)

        has_loop = any(p.search(norm) for p in _INFINITE_LOOP_OPENERS)
        has_spawn = any(p.search(norm) for p in _SPAWN_CALLS)
        if has_loop and has_spawn:
            has_break = any(p.search(norm) for p in _BREAK_INDICATORS)
            if has_break:
                return ScanResult(
                    Verdict.WARNING,
                    "Endlosschleife mit Prozess-/Fenster-Erzeugung erkannt, aber eine mögliche "
                    "Abbruchbedingung ist vorhanden - bitte manuell prüfen, ob sie zuverlässig greift.",
                )
            return ScanResult(
                Verdict.BLOCKED,
                "Endlosschleife ohne erkennbare Abbruchbedingung kombiniert mit Prozess-/Fenster-"
                "Erzeugung - klassisches Ressourcen-Erschöpfungs-Muster (siehe Vorfall vom 2026-07-15).",
            )

        if _depth < _MAX_BASE64_RECURSION_DEPTH:
            for decoded in self._decode_base64_runs(code):
                nested = self.scan_output(decoded, _depth + 1)
                if nested.verdict != Verdict.SAFE:
                    return ScanResult(
                        nested.verdict,
                        f"In Base64 verstecktes Muster: {nested.reason}",
                    )

        return ScanResult(Verdict.SAFE)

    @staticmethod
    def _decode_base64_runs(text: str) -> list[str]:
        """Extract long base64-looking runs and decode the ones that yield text."""
        decoded_texts: list[str] = []
        for match in _BASE64_RUN_RE.finditer(text):
            token = match.group(0)
            # Base64 length must be a multiple of 4 to be valid; trim the remainder
            # rather than reject, so padded and unpadded blocks both decode.
            trimmed = token[: len(token) - (len(token) % 4)]
            if len(trimmed) < _MIN_BASE64_RUN:
                continue
            try:
                raw = base64.b64decode(trimmed, validate=True)
            except (binascii.Error, ValueError):
                continue
            try:
                as_text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            # Ignore decodes that are mostly non-printable (random hashes/keys),
            # keep ones that look like smuggled commands/text.
            printable = sum(c.isprintable() or c in "\n\t\r" for c in as_text)
            if as_text and printable / len(as_text) >= 0.85:
                decoded_texts.append(as_text)
        return decoded_texts

    # --- Public boolean API (as specified in the plan). ---

    def is_input_safe(self, text: str) -> tuple[bool, str | None]:
        result = self.scan_input(text)
        if result.verdict == Verdict.BLOCKED:
            log.warning("Eingabe blockiert (Sicherheitsfilter): %s", result.reason)
            return False, result.reason
        return True, None

    def is_prompt_injection_safe(self, text: str) -> tuple[bool, str | None]:
        result = self.scan_prompt_injection(text)
        if result.verdict == Verdict.BLOCKED:
            log.warning("Prompt-Injection-Versuch erkannt: %s", result.reason)
            return False, result.reason
        return True, None

    def is_output_safe(self, code: str) -> tuple[bool, str | None]:
        """BLOCKED -> unsafe. WARNING is treated as safe-but-flagged (caller may
        surface the reason) since a regex cannot reason about control flow."""
        result = self.scan_output(code)
        if result.verdict == Verdict.BLOCKED:
            log.warning("Ausgabe blockiert (Sicherheitsfilter): %s", result.reason)
            return False, result.reason
        return True, result.reason  # reason is set for WARNING, None for SAFE

    def scan_markdown_code_blocks(self, response_text: str) -> list[ScanResult]:
        """Scan each fenced code block in an LLM response individually."""
        return [self.scan_output(m.group(1)) for m in _CODE_BLOCK_RE.finditer(response_text)]


# Process-wide singleton + module-level convenience functions.
_default = TarnoSecurity()


def is_input_safe(text: str) -> tuple[bool, str | None]:
    return _default.is_input_safe(text)


def is_prompt_injection_safe(text: str) -> tuple[bool, str | None]:
    return _default.is_prompt_injection_safe(text)


def is_output_safe(code: str) -> tuple[bool, str | None]:
    return _default.is_output_safe(code)
