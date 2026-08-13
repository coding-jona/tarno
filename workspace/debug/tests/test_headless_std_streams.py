"""Regression test for the headless std stream fallback."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from tarno_backend.__main__ import _ensure_headless_std_streams


class HeadlessStdStreamTests(unittest.TestCase):
    """In a PyInstaller windowed build (console=False) sys.stdin/stdout/stderr
    are None; aider accesses .encoding and .isatty() on them, which crashed the
    Agent-Pool-Lauf with 'NoneType' object has no attribute 'encoding'."""

    def test_ensure_headless_std_streams_sets_null_devices(self) -> None:
        with patch.object(sys, "stdin", None), \
             patch.object(sys, "stdout", None), \
             patch.object(sys, "stderr", None):
            _ensure_headless_std_streams()
            self.assertIsNotNone(sys.stdin)
            self.assertIsNotNone(sys.stdout)
            self.assertIsNotNone(sys.stderr)
            self.assertEqual(sys.stdin.encoding, "utf-8")
            self.assertEqual(sys.stdout.encoding, "utf-8")
            self.assertEqual(sys.stderr.encoding, "utf-8")
            # aider/run_cmd.py calls sys.stdin.isatty() and sys.stdout.isatty()
            self.assertFalse(sys.stdin.isatty())
            self.assertFalse(sys.stdout.isatty())
            self.assertFalse(sys.stderr.isatty())


if __name__ == "__main__":
    unittest.main()
