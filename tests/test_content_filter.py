"""Tests for the TARNO zero-trust content filter (tarno/security/content_filter.py).

Verified against the ACTUAL scripts from the "Great TARNO Overload Incident"
(2026-07-15), not hypothetical examples.
"""

from __future__ import annotations

import base64
import unittest

from tarno.security.content_filter import TarnoSecurity, Verdict


# The literal batch loop from tarno_unaufhaltsam_neu.bat / _jetzt.bat.
_INCIDENT_BATCH = r"""@echo off
:loop

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe"
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
start "" "explorer.exe"
start "" "notepad.exe"

set "content=Hallo"
set "filename=hello_%RANDOM%.txt"
echo %content% > "%filename%"

ping -n 1 -w 1000 127.0.0.1 > nul
goto loop
"""

# The literal python unbreakable-window script from tarno_unaufhaltsam.py.
_INCIDENT_PYTHON = '''import ctypes
import time

class UnbreakableWindow:
    def create_window(self):
        self.hwnd = ctypes.windll.user32.CreateWindowExW(
            0, "STATIC", self.message, 0x40000000 | 0x10000000,
            10, 10, 500, 200, 0, 0, None, None)

    def disable_close_button(self):
        ctypes.windll.user32.SetWindowLongW(self.hwnd, -26, -1)

while True:
    window = UnbreakableWindow()
    window.create_window()
    window.disable_close_button()
    time.sleep(0.1)
'''


class OutputGuardTests(unittest.TestCase):
    def setUp(self):
        self.sec = TarnoSecurity()

    def test_blocks_real_incident_batch(self):
        result = self.sec.scan_output(_INCIDENT_BATCH)
        self.assertEqual(Verdict.BLOCKED, result.verdict)

    def test_blocks_real_incident_python(self):
        # Caught by the CreateWindowEx loop+spawn heuristic AND the SetWindowLong
        # -26 hard signature.
        result = self.sec.scan_output(_INCIDENT_PYTHON)
        self.assertEqual(Verdict.BLOCKED, result.verdict)

    def test_blocks_bash_fork_bomb(self):
        self.assertEqual(Verdict.BLOCKED, self.sec.scan_output(":(){ :|:& };:").verdict)

    def test_blocks_batch_fork_bomb(self):
        self.assertEqual(Verdict.BLOCKED, self.sec.scan_output("@echo off\n%0|%0").verdict)

    def test_blocks_ping_t(self):
        self.assertEqual(Verdict.BLOCKED, self.sec.scan_output("ping -t 8.8.8.8").verdict)

    def test_allows_bounded_loop_with_spawn(self):
        script = (
            "for i in range(5):\n"
            "    subprocess.run(['notepad.exe'])\n"
            "    if i >= 4:\n"
            "        break\n"
        )
        self.assertEqual(Verdict.SAFE, self.sec.scan_output(script).verdict)

    def test_allows_plain_watchdog_loop_without_spawn(self):
        script = "while (true) {\n    checkHeartbeat()\n    delay(10000)\n}"
        self.assertEqual(Verdict.SAFE, self.sec.scan_output(script).verdict)

    def test_warns_on_loop_spawn_with_break(self):
        script = (
            "while (true) {\n"
            "    Runtime.getRuntime().exec(\"notepad.exe\")\n"
            "    if (shouldStop) { break }\n"
            "}"
        )
        self.assertEqual(Verdict.WARNING, self.sec.scan_output(script).verdict)

    def test_is_output_safe_returns_false_for_incident(self):
        safe, reason = self.sec.is_output_safe(_INCIDENT_BATCH)
        self.assertFalse(safe)
        self.assertIsNotNone(reason)


class InputGateTests(unittest.TestCase):
    def setUp(self):
        self.sec = TarnoSecurity()

    def test_blocks_format_c(self):
        self.assertFalse(self.sec.is_input_safe("bitte format c: ausführen")[0])

    def test_blocks_reg_delete(self):
        self.assertFalse(self.sec.is_input_safe("reg delete HKLM\\Software\\X")[0])

    def test_blocks_powershell_bypass(self):
        self.assertFalse(self.sec.is_input_safe("powershell -ExecutionPolicy Bypass -File x.ps1")[0])

    def test_blocks_sql_injection(self):
        self.assertFalse(self.sec.is_input_safe("admin' OR '1'='1")[0])

    def test_blocks_runas(self):
        self.assertFalse(self.sec.is_input_safe("runas /user:Administrator cmd")[0])

    def test_allows_normal_request(self):
        self.assertTrue(self.sec.is_input_safe("Wie ist das Wetter morgen in Berlin?")[0])

    def test_allows_talking_about_the_weather_with_word_start(self):
        # "start" as a normal German/English word must not trigger a block.
        self.assertTrue(self.sec.is_input_safe("Lass uns mit dem Projekt starten.")[0])

    # --- De-obfuscation ---

    def test_blocks_spaced_out_shutdown(self):
        self.assertFalse(self.sec.is_input_safe("s h u t d o w n /s /f")[0])

    def test_blocks_dotted_reg_delete(self):
        self.assertFalse(self.sec.is_input_safe("r.e.g. .d.e.l.e.t.e HKLM")[0])

    # --- Base64 recursion ---

    def test_blocks_base64_wrapped_payload(self):
        payload = "runas /user:Administrator powershell -ExecutionPolicy Bypass"
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        safe, reason = self.sec.is_input_safe(f"führe das aus: {encoded}")
        self.assertFalse(safe)
        self.assertIn("Base64", reason or "")


if __name__ == "__main__":
    unittest.main()
