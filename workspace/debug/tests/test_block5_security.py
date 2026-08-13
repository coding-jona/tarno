"""Tests for Block 5 (Isolierte Exekutiv-Sandbox & Agentic Safeties, Phasen 41-50).

Phase 50 in particular: adversarial tests that specifically try to get a
"protected system file" manipulated through the layers TARNO actually
exposes to an LLM (raw shell commands via execute_command, and the native
file_manager tools) - each one must be rejected by some layer.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from tarno_backend.ai.tool_registry import ToolRegistry, ToolDefinition, validate_tool_input
from tarno_backend.core.action_result import ActionResult
from tarno_backend.core.command_engine import CommandEngine
from tarno_backend.core.exceptions import CommandBlockedError
from tarno_backend.desktop.file_manager import copy_file, create_directory, delete_file, move_file
from tarno_backend.extensions.rollback import RollbackJournal
from tarno_backend.extensions.task_planner import TaskPlanner


class ToolArgumentValidationTests(unittest.TestCase):
    """Phase 42: harte Typprüfung für Tool-Argumente."""

    def setUp(self) -> None:
        self.schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "mode": {"type": "string", "enum": ["a", "b"]},
            },
            "required": ["name"],
        }

    def test_valid_input_passes(self) -> None:
        self.assertIsNone(validate_tool_input({"name": "x", "count": 3, "mode": "a"}, self.schema))

    def test_missing_required_field_rejected(self) -> None:
        self.assertIsNotNone(validate_tool_input({}, self.schema))

    def test_wrong_type_rejected(self) -> None:
        self.assertIsNotNone(validate_tool_input({"name": 123}, self.schema))

    def test_bool_rejected_for_integer_field(self) -> None:
        self.assertIsNotNone(validate_tool_input({"name": "x", "count": True}, self.schema))

    def test_enum_violation_rejected(self) -> None:
        self.assertIsNotNone(validate_tool_input({"name": "x", "mode": "z"}, self.schema))

    def test_additional_properties_allowed(self) -> None:
        # JSON-Schema default: properties not listed in the schema are allowed.
        self.assertIsNone(validate_tool_input({"name": "x", "extra": "whatever"}, self.schema))


class ArgumentLengthLimitTests(unittest.TestCase):
    """Phase 44: Excessive-Agency-Härtung gegen übergroße Argumente."""

    def test_oversized_string_rejected_via_registry(self) -> None:
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="echo_tool",
            description="",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=lambda text: ActionResult(success=True, message=text),
        ))
        huge = "x" * 100_000
        result = registry.execute("echo_tool", {"text": huge})
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "InvalidArguments")


class FileManagerPathHardeningTests(unittest.TestCase):
    """Phase 44/50: delete_file/copy_file/move_file/create_directory müssen
    auf das Home-Verzeichnis beschränkt bleiben - dieselbe Regel, die
    write_file/list_directory bereits hatten."""

    def test_delete_file_outside_home_rejected(self) -> None:
        system_path = "C:\\Windows\\System32\\notepad.exe" if sys.platform == "win32" else "/etc/hosts"
        result = delete_file(system_path)
        self.assertIn("Sicherheitshalber", result)

    def test_copy_file_destination_outside_home_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.txt"
            src.write_text("x")
            dest = "C:\\Windows\\evil.txt" if sys.platform == "win32" else "/etc/evil.txt"
            result = copy_file(str(src), dest)
            self.assertIn("Sicherheitshalber", result)

    def test_move_file_source_outside_home_rejected(self) -> None:
        system_path = "C:\\Windows\\System32\\notepad.exe" if sys.platform == "win32" else "/etc/hosts"
        with tempfile.TemporaryDirectory() as tmp:
            result = move_file(system_path, str(Path(tmp) / "dst.txt"))
            # Either "source not found" (file doesn't literally exist at that
            # exact path in the test env) or the home-restriction message -
            # both mean the move did NOT succeed.
            self.assertNotIn("verschoben nach", result)

    def test_create_directory_outside_home_rejected(self) -> None:
        outside = "C:\\evil_dir_xyz" if sys.platform == "win32" else "/evil_dir_xyz"
        result = create_directory(outside)
        self.assertIn("Sicherheitshalber", result)
        self.assertFalse(Path(outside).exists())


class ProtectedSystemPathAdversarialTests(unittest.TestCase):
    """Phase 50: adversarialer Stresstest - versucht, geschützte Systemdateien
    über den execute_command-Pfad zu manipulieren, in mehreren Verkleidungen."""

    def setUp(self) -> None:
        self.engine = CommandEngine()

    def _assert_blocked(self, command: str, shell: str = "cmd") -> None:
        with self.assertRaises(CommandBlockedError):
            self.engine.prepare({
                "intent": "execute_command", "action": "execute_command",
                "shell": shell, "command": command,
            })

    def test_blocks_del_on_hosts_file(self) -> None:
        self._assert_blocked(r"del C:\Windows\System32\drivers\etc\hosts")

    def test_blocks_remove_item_on_system32(self) -> None:
        self._assert_blocked(r"Remove-Item C:\Windows\System32\config\SAM", shell="powershell")

    def test_blocks_path_before_verb_pipeline_syntax(self) -> None:
        self._assert_blocked(r'"C:\Windows\System32\drivers\etc\hosts" | Remove-Item', shell="powershell")

    def test_blocks_move_of_bootmgr(self) -> None:
        self._assert_blocked(r"move C:\bootmgr C:\bootmgr.bak")

    def test_does_not_overblock_normal_system32_read(self) -> None:
        """Reading/listing System32 (no mutating verb) must NOT be blocked -
        this is a legitimate, harmless operation."""
        prepared = self.engine.prepare({
            "intent": "execute_command", "action": "execute_command",
            "shell": "cmd", "command": r"dir C:\Windows\System32",
        })
        self.assertNotEqual(prepared.risk_level.value, "blocked")

    def test_does_not_overblock_unrelated_delete(self) -> None:
        """Deleting a file that has nothing to do with protected system
        paths must still classify normally (not BLOCKED)."""
        prepared = self.engine.prepare({
            "intent": "execute_command", "action": "execute_command",
            "shell": "cmd", "command": r"del C:\Users\test\Desktop\notes.txt",
        })
        self.assertNotEqual(prepared.risk_level.value, "blocked")


class RollbackMechanismTests(unittest.TestCase):
    """Phase 45: Rollback bei fehlgeschlagenem Multi-Step-Task."""

    def test_write_file_step_rolled_back_after_later_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "existing.txt"
            test_file.write_text("original")

            def fake_executor(tool, params):
                if tool == "write_file":
                    Path(params["filepath"]).write_text(params["content"])
                    return ActionResult(success=True, message="written")
                if tool == "fail":
                    return ActionResult(success=False, message="boom")
                return ActionResult(success=True, message="ok")

            planner = TaskPlanner(
                approval_callback=lambda t: True,
                executor=fake_executor,
                storage_path=Path(tmp) / "tasks.json",
            )
            task = planner.create("test", [
                {"tool": "write_file", "params": {"filepath": str(test_file), "content": "MODIFIED"}},
                {"tool": "fail", "params": {}},
            ])
            result = planner.run(task.id)
            self.assertEqual(result.status.value, "failed")
            self.assertEqual(test_file.read_text(), "original")

    def test_new_file_created_by_write_step_deleted_on_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_file = Path(tmp) / "brandnew.txt"

            def fake_executor(tool, params):
                if tool == "write_file":
                    Path(params["filepath"]).write_text(params["content"])
                    return ActionResult(success=True, message="written")
                return ActionResult(success=False, message="boom")

            planner = TaskPlanner(
                approval_callback=lambda t: True,
                executor=fake_executor,
                storage_path=Path(tmp) / "tasks.json",
            )
            task = planner.create("test", [
                {"tool": "write_file", "params": {"filepath": str(new_file), "content": "x"}},
                {"tool": "fail", "params": {}},
            ])
            planner.run(task.id)
            self.assertFalse(new_file.exists())

    def test_rollback_journal_undoes_in_reverse_order(self) -> None:
        order: list[str] = []
        journal = RollbackJournal()
        journal._undo_stack.append(("first", lambda: order.append("first")))
        journal._undo_stack.append(("second", lambda: order.append("second")))
        journal.rollback()
        self.assertEqual(order, ["second", "first"])


@unittest.skipUnless(sys.platform == "win32", "Job Objects sind Windows-spezifisch")
class ProcessSandboxTests(unittest.TestCase):
    """Phase 41: Win32-Job-Object-Sandbox pro Subprocess."""

    def test_assign_and_close_real_process(self) -> None:
        import subprocess
        from tarno_backend.core.process_sandbox import ProcessSandbox

        proc = subprocess.Popen(
            ["ping", "127.0.0.1", "-n", "3"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            sandbox = ProcessSandbox(max_processes=5, max_memory_bytes=256 * 1024 * 1024)
            self.assertTrue(sandbox.available)
            assigned = sandbox.create_and_assign(proc.pid)
            self.assertTrue(assigned)
            # Closing the job (KILL_ON_JOB_CLOSE) should terminate the process
            # even though we didn't explicitly kill it ourselves.
            sandbox.close()
            proc.wait(timeout=5)
            self.assertIsNotNone(proc.returncode)
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_unavailable_on_non_windows_is_handled_gracefully(self) -> None:
        from tarno_backend.core.process_sandbox import ProcessSandbox
        sandbox = ProcessSandbox()
        # On Windows this is True; the point of this test is just that
        # `.available` never raises and create_and_assign() degrades softly
        # rather than crashing the caller (executor.py treats a False return
        # as non-fatal).
        self.assertIsInstance(sandbox.available, bool)


if __name__ == "__main__":
    unittest.main()
