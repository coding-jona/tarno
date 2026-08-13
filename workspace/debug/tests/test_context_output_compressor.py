"""Tests for tarno/ai/context/output_compressor.py (Kontext-Effizienz Phase 1)."""

from __future__ import annotations

import unittest

from tarno_backend.ai.context.output_compressor import (
    CompressorConfig,
    compress_tool_output,
    compress_tool_output_detailed,
)


class ShortInputNoOpTests(unittest.TestCase):
    def test_short_plain_text_is_returned_unchanged(self) -> None:
        text = "Datei erfolgreich gespeichert."
        self.assertEqual(compress_tool_output(text), text)

    def test_empty_string_returned_unchanged(self) -> None:
        self.assertEqual(compress_tool_output(""), "")


class DedupeTests(unittest.TestCase):
    def test_repeated_identical_lines_collapse_with_count(self) -> None:
        text = "\n".join(["a"] * 25)
        result, info = compress_tool_output_detailed(text)
        self.assertIn("a (×25)", result)
        self.assertIn("dedupe", info.strategy_notes)

    def test_near_identical_lines_differing_only_by_number_collapse(self) -> None:
        """Matches RTK's real-world example: 200+ near-identical PASSED
        lines (differing only by an incrementing test id) collapse to one
        representative line with a count, not 200 distinct kept lines."""
        lines = [f"test_ok_{i} ... PASSED" for i in range(180)]
        text = "\n".join(lines)
        result, info = compress_tool_output_detailed(text)
        self.assertIn("test_ok_0 ... PASSED (×180)", result)
        self.assertNotIn("test_ok_179", result)
        self.assertLess(len(result), len(text) / 10)

    def test_distinct_lines_are_not_merged(self) -> None:
        """Lines differing by more than just a number (i.e. genuinely
        different content, not the same repeated shape) must survive
        individually - only near-identical/templated repeats collapse."""
        topics = [
            "database", "network", "filesystem", "cache", "auth",
            "scheduler", "renderer", "parser", "logger", "config",
        ]
        text = "\n".join(f"unique line about {topic} subsystem" for topic in topics)
        result, _ = compress_tool_output_detailed(text)
        for topic in topics:
            self.assertIn(topic, result)


class GroupingTests(unittest.TestCase):
    def test_many_compiler_errors_in_one_file_are_grouped(self) -> None:
        """Messages differ by more than a number (distinct undefined names),
        so dedupe's digit-normalization can't collapse them - this isolates
        the grouping strategy specifically, rather than dedupe achieving
        the same result first."""
        names = [
            "bar", "baz", "qux", "spam", "eggs", "foo", "quux", "corge",
            "grault", "garply", "waldo", "fred", "plugh", "xyzzy", "thud",
            "alpha", "beta", "gamma", "delta", "epsilon",
        ]
        lines = [f"src/foo.py:{10 + i}: error: undefined name '{name}'" for i, name in enumerate(names)]
        text = "\n".join(lines)
        result, info = compress_tool_output_detailed(text)
        self.assertIn("Vorkommen", result)
        self.assertIn("weitere", result)
        self.assertIn("group", info.strategy_notes)

    def test_few_matches_are_kept_inline_not_grouped(self) -> None:
        text = "\n".join(
            [f"src/foo.py:{10 + i}: error: x" for i in range(2)] + ["ok: nothing else happened"]
        )
        result, _ = compress_tool_output_detailed(text)
        self.assertNotIn("Vorkommen", result)


def _index_to_letters(i: int) -> str:
    """Digit-free index encoding so lines stay distinct even after the
    dedupe stage's digit-normalization (see _normalize_for_dedupe)."""
    letters = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        letters = chr(97 + rem) + letters
    return letters


class TruncationTests(unittest.TestCase):
    def test_still_too_long_after_dedupe_group_gets_truncated(self) -> None:
        text = "\n".join(f"unique distinct line marker {_index_to_letters(i)}" for i in range(500))
        cfg = CompressorConfig(max_chars=500)
        result, info = compress_tool_output_detailed(text, config=cfg)
        self.assertLessEqual(len(result), 500)
        self.assertIn("gekürzt", result)
        self.assertIn("truncate", info.strategy_notes)

    def test_truncation_keeps_head_and_tail(self) -> None:
        text = "\n".join(f"unique distinct line marker {_index_to_letters(i)}" for i in range(500))
        cfg = CompressorConfig(max_chars=500)
        result, _ = compress_tool_output_detailed(text, config=cfg)
        self.assertIn(f"marker {_index_to_letters(0)}", result)
        self.assertIn(f"marker {_index_to_letters(499)}", result)


class FilterTests(unittest.TestCase):
    def test_ansi_escape_codes_are_stripped(self) -> None:
        text = "\n".join([f"\x1b[32mok {i}\x1b[0m" for i in range(25)])
        result, info = compress_tool_output_detailed(text)
        self.assertNotIn("\x1b[", result)

    def test_npm_warn_noise_lines_are_dropped(self) -> None:
        lines = ["npm warn deprecated foo@1.0.0"] * 5 + ["real output line"] * 25
        text = "\n".join(lines)
        result, _ = compress_tool_output_detailed(text)
        self.assertNotIn("npm warn", result)
        self.assertIn("real output line", result)


if __name__ == "__main__":
    unittest.main()
