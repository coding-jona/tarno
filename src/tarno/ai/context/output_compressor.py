"""RTK-inspirierte Tool-Output-Kompression (github.com/rtk-ai/rtk).

Reine Python-Neuimplementierung der vier RTK-Strategien - KEIN Subprocess-
Aufruf des echten Rust-Binaries (das hat keine Python-Library und TARNO
muss auf beliebigen Endnutzer-Windows-Installationen ohne Zusatz-Install
laufen). Reihenfolge folgt RTKs eigener Pipeline: Filtern vor Gruppieren
vermeidet, dass Rauschen die Gruppierungs-Heuristiken verfaelscht.

Wird an der Stelle angewendet, wo Tool-/Kommandoausgaben zurueck in einen
LLM-Kontext fliessen (siehe tarno/core/engine.py add_tool_result-Aufrufe,
tarno/core/command_tool.py), NICHT an Stellen, die nur an die UI streamen
(z.B. CodingOutput - erreicht heute keinen LLM-Kontext, siehe Kontext-
Effizienz-Plan Phase 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ANSI escape sequences (Farbcodes, Cursor-Bewegung) - reines Steuerzeichen-
# Rauschen ohne Informationswert fuer ein LLM.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Bekannte reine Rauschen-Zeilen (Paketmanager-Boilerplate). Bewusst kurz
# gehalten und konservativ - im Zweifel wird eine unbekannte Zeile behalten,
# nicht verworfen.
_NOISE_LINE_PATTERNS = (
    re.compile(r"^\s*npm warn\b", re.IGNORECASE),
    re.compile(r"^\s*requirement already satisfied\b", re.IGNORECASE),
)

# "datei:zeile[:spalte]: level: nachricht" - deckt gcc/clang/tsc/mypy/
# eslint-artige Compiler-/Linter-Meldungen ab.
_FILE_LOCATION_RE = re.compile(
    r"^(?P<file>[^\s:][^:]*):(?P<line>\d+)(?::(?P<col>\d+))?:\s*"
    r"(?P<level>error|warning|Error|Warning|ERROR|WARNING)\b[:\s]*(?P<msg>.*)$"
)
# pytest-Fehlschlagszeilen: "FAILED tests/test_x.py::test_y - AssertionError: ..."
_PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(?P<test>\S+)")
# Generische ERROR/WARNING-Zeilen ohne Dateiangabe (z.B. Logging-Ausgabe).
_GENERIC_LEVEL_RE = re.compile(r"^(?P<level>ERROR|WARNING|WARN)\b[:\s]*(?P<msg>.*)$")

_GROUP_MAX_EXAMPLES = 3


@dataclass
class CompressorConfig:
    """Schwellenwerte/Verhalten - anpassbar ohne Codeaenderung."""

    max_chars: int = 4000
    dedupe_lookback: int = 50
    group_max_examples: int = _GROUP_MAX_EXAMPLES
    truncate_head_ratio: float = 0.6


@dataclass
class CompressionResult:
    """Debug-/Logging-Metadaten zu einem Kompressionslauf (siehe Phase 6)."""

    original_chars: int
    compressed_chars: int
    strategy_notes: list[str] = field(default_factory=list)


_DEFAULT_CONFIG = CompressorConfig()


def compress_tool_output(
    text: str,
    *,
    tool_name: str = "",
    max_chars: int = 4000,
    config: CompressorConfig | None = None,
) -> str:
    """Komprimiert mehrzeiligen Tool-Output fuer den Weg zurueck ins LLM.

    Frueher Ausstieg bei bereits kurzem/unstrukturiertem Text - kein
    Overhead fuer normale kurze Tool-Ergebnisse.
    """
    compressed, _ = compress_tool_output_detailed(
        text, tool_name=tool_name, max_chars=max_chars, config=config
    )
    return compressed


def compress_tool_output_detailed(
    text: str,
    *,
    tool_name: str = "",
    max_chars: int = 4000,
    config: CompressorConfig | None = None,
) -> tuple[str, CompressionResult]:
    """Wie compress_tool_output, gibt zusaetzlich Kompressions-Metadaten
    zurueck (fuer das aggressive Debug-Logging in Phase 6)."""
    cfg = config or CompressorConfig(max_chars=max_chars)
    original_chars = len(text)
    notes: list[str] = []

    # Frueher Ausstieg NUR fuer wirklich kurzen/unstrukturierten Text - ein
    # Schwellenwert von 20 Zeilen wuerde genau die Faelle verpassen, die
    # komprimiert werden sollen (z.B. 20 gleichartige PASSED-Zeilen).
    if not text or (original_chars <= 500 and text.count("\n") < 8):
        return text, CompressionResult(original_chars, original_chars, notes)

    lines = text.splitlines()

    lines, changed = _filter_noise(lines)
    if changed:
        notes.append("filter")

    lines, changed = _dedupe_lines(lines, cfg.dedupe_lookback)
    if changed:
        notes.append("dedupe")

    lines, changed = _group_by_pattern(lines, cfg.group_max_examples)
    if changed:
        notes.append("group")

    result_text = "\n".join(lines)
    if len(result_text) > cfg.max_chars:
        result_text = _truncate_middle(result_text, cfg.max_chars, cfg.truncate_head_ratio)
        notes.append("truncate")

    return result_text, CompressionResult(original_chars, len(result_text), notes)


def _filter_noise(lines: list[str]) -> tuple[list[str], bool]:
    changed = False
    out: list[str] = []
    prev_blank = False
    for raw_line in lines:
        line = _ANSI_ESCAPE_RE.sub("", raw_line)
        if line != raw_line:
            changed = True

        if any(p.match(line) for p in _NOISE_LINE_PATTERNS):
            changed = True
            continue

        is_blank = not line.strip()
        if is_blank and prev_blank:
            changed = True
            continue
        prev_blank = is_blank
        out.append(line)
    return out, changed


_DIGIT_RE = re.compile(r"\d+")


def _normalize_for_dedupe(line: str) -> str:
    """Collapses varying numbers/ids to '#' so lines that only differ by an
    incrementing test-name/id (e.g. "test_ok_0 ... PASSED", "test_ok_1 ...
    PASSED") are recognized as the same repeated shape - matches RTK's
    real-world example (200+ near-identical PASSED lines -> ~20 lines)."""
    return _DIGIT_RE.sub("#", line.strip())


def _dedupe_lines(lines: list[str], lookback: int) -> tuple[list[str], bool]:
    changed = False
    out: list[str] = []
    # normalized-template -> index in `out` of its representative line
    recent: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue

        template = _normalize_for_dedupe(line)
        prev_idx = recent.get(template)
        if prev_idx is not None and (len(out) - prev_idx) <= lookback:
            prev = out[prev_idx]
            m = re.match(r"^(?P<base>.*) \(×(?P<count>\d+)\)$", prev)
            if m:
                count = int(m.group("count")) + 1
                out[prev_idx] = f"{m.group('base')} (×{count})"
            else:
                out[prev_idx] = f"{prev} (×2)"
            changed = True
            continue

        out.append(line)
        recent[template] = len(out) - 1

    return out, changed


def _classify(line: str) -> tuple[str, str] | None:
    """Returns (group_key, example_text) if the line matches a groupable
    error/warning shape, else None."""
    m = _FILE_LOCATION_RE.match(line)
    if m:
        return f"{m.group('level').lower()}:{m.group('file')}", line

    m = _PYTEST_FAILED_RE.match(line)
    if m:
        return "pytest-failed", line

    m = _GENERIC_LEVEL_RE.match(line)
    if m:
        return f"{m.group('level').lower()}", line

    return None


def _group_by_pattern(lines: list[str], max_examples: int) -> tuple[list[str], bool]:
    groups: dict[str, list[str]] = {}
    group_order: list[str] = []
    out: list[str] = []
    changed = False

    for line in lines:
        classified = _classify(line)
        if classified is None:
            out.append(line)
            continue
        key, example = classified
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append(example)
        out.append(f"\x00GROUP\x00{key}")  # placeholder, resolved below

    # Only actually group keys that appeared more than max_examples times -
    # a single/handful of matching lines are kept inline, unmodified.
    keys_to_group = {k for k, v in groups.items() if len(v) > max_examples}
    if not keys_to_group:
        return lines, False

    resolved: list[str] = []
    emitted: set[str] = set()
    for line in out:
        if line.startswith("\x00GROUP\x00"):
            key = line[len("\x00GROUP\x00"):]
            if key not in keys_to_group:
                # Not grouped - restore the original example in order.
                resolved.append(groups[key].pop(0))
                continue
            changed = True
            if key in emitted:
                continue
            emitted.add(key)
            examples = groups[key]
            block = [f"{key} ({len(examples)} Vorkommen):"]
            for ex in examples[:max_examples]:
                block.append(f"  - {ex}")
            remaining = len(examples) - max_examples
            if remaining > 0:
                block.append(f"  ... ({remaining} weitere)")
            resolved.extend(block)
        else:
            resolved.append(line)

    return resolved, changed


def _truncate_middle(text: str, max_chars: int, head_ratio: float) -> str:
    if len(text) <= max_chars:
        return text
    marker = "\n... (gekürzt) ...\n"
    budget = max_chars - len(marker)
    if budget <= 0:
        return text[:max_chars]
    head_len = int(budget * head_ratio)
    tail_len = budget - head_len
    return text[:head_len] + marker + text[-tail_len:] if tail_len > 0 else text[:max_chars]


if __name__ == "__main__":
    _demo_lines = ["Running 210 tests..."]
    for i in range(180):
        _demo_lines.append(f"test_ok_{i} ... PASSED")
    for i in range(5):
        _demo_lines.append(f"src/foo.py:{10 + i}: error: undefined name 'bar'")
    _demo_lines.append("FAILED tests/test_x.py::test_y - AssertionError: 1 != 2")
    _demo_lines.append("FAILED tests/test_z.py::test_w - AssertionError: 3 != 4")
    _demo_text = "\n".join(_demo_lines)

    _compressed, _result = compress_tool_output_detailed(_demo_text, tool_name="pytest")
    print(_compressed)
    print("---")
    print(
        f"original={_result.original_chars} compressed={_result.compressed_chars} "
        f"strategies={_result.strategy_notes}"
    )
