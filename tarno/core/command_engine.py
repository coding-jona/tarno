"""Central command execution engine for TARNO.

The engine receives structured action requests from the LLM, validates them,
classifies their risk level, blocks dangerous patterns and prepares them for
safe execution by the ShellExecutor.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tarno.core.action_result import ActionResult
from tarno.core.exceptions import CommandBlockedError
from tarno.security.content_filter import is_output_safe

log = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PreparedCommand:
    """A validated and risk-assessed command ready for execution."""

    action: str
    shell: str
    command: str
    params: dict[str, Any]
    risk_level: RiskLevel
    intent: str
    user_query: str
    timeout: float
    explanation: str


# Risk classification per intent/pattern. Lower entries have higher priority.
_BLOCKED_PATTERNS = [
    # Code execution / reflective invocation
    r"invoke-expression",
    r"\biex\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"base64",
    # Admin / disk / registry destruction
    r"format-volume",
    r"clear-disk",
    r"diskpart",
    r"reg\s+delete\s+.*\\",
    r"remove-item\s+-recurse\s+([a-z]:\\\\|\\\\|/)",
    r"rm\s+-rf\s+/",
    r"del\s+/[fqs]",
    # Elevation attempts
    r"start-process\s+.*-verb\s+runas",
    r"runas\s+/user:",
    # Credential / token theft
    r"get-wmicobject\s+.*win32_process.*create",
    r"mimikatz",
    r"sekurlsa",
]

# Block 5, Phase 50 (adversarialer Stresstest): a raw shell command that
# mutates a well-known protected system path (e.g. "del C:\Windows\System32\
# drivers\etc\hosts") previously fell through to RiskLevel.MEDIUM via the
# generic execute_command fallback in assess_risk() below - which
# AutonomyMode.BALANCED (the default since Block 2) auto-grants WITHOUT a
# confirmation dialog. Path and verb are checked independently (not as one
# adjacent regex) since PowerShell/pipeline syntax can put either one first
# (e.g. `"C:\...\hosts" | Remove-Item`) - mirrors the has_loop/has_spawn
# combinational check already used in content_filter.py for the same reason.
_PROTECTED_PATH_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"windows\\system32", r"windows\\syswow64", r"windows\\boot",
        r"\\drivers\\etc\\hosts\b", r"\bboot\.ini\b", r"\bbootmgr\b",
        r"\bntldr\b", r"\bpagefile\.sys\b", r"\bhiberfil\.sys\b",
        r"/etc/", r"/boot/", r"/sys/",
    ]
]
_MUTATING_VERB_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bdel\b", r"\berase\b", r"\bremove-item\b", r"\brm\b",
        r"\bmove-item\b", r"\bmove\b", r"\bren\b", r"\brename\b",
        r"\bset-content\b", r"\bout-file\b", r"\bclear-content\b",
    ]
]


def _targets_protected_system_path(lower_command: str) -> bool:
    """True if *lower_command* (already lowercased) both references a
    well-known protected system path AND uses a mutating verb, regardless
    of which comes first in the command text."""
    has_protected_path = any(p.search(lower_command) for p in _PROTECTED_PATH_PATTERNS)
    has_mutating_verb = any(p.search(lower_command) for p in _MUTATING_VERB_PATTERNS)
    return has_protected_path and has_mutating_verb

_RISK_INTENTS: dict[str, RiskLevel] = {
    "open_application": RiskLevel.LOW,
    "open_file": RiskLevel.LOW,
    "open_browser": RiskLevel.LOW,
    "take_screenshot": RiskLevel.LOW,
    "get_system_info": RiskLevel.LOW,
    "web_search": RiskLevel.LOW,
    "write_file": RiskLevel.MEDIUM,
    "copy_file": RiskLevel.MEDIUM,
    "move_file": RiskLevel.MEDIUM,
    "delete_file": RiskLevel.MEDIUM,
    "create_directory": RiskLevel.MEDIUM,
    "software_install": RiskLevel.MEDIUM,
    "software_remove": RiskLevel.MEDIUM,
    "system_update": RiskLevel.MEDIUM,
    "shutdown": RiskLevel.HIGH,
    "reboot": RiskLevel.HIGH,
    "format_disk": RiskLevel.BLOCKED,
    "modify_registry": RiskLevel.HIGH,
    "execute_command": RiskLevel.MEDIUM,  # individual command risk is refined below
}

_HIGH_RISK_KEYWORDS = [
    "shutdown",
    "restart-computer",
    "stop-computer",
    "reboot",
    "format",
    "diskpart",
    "reg ",
    "remove-item -recurse",
    "rm -rf",
    "bcdedit",
    "cipher /w",
]


class CommandEngine:
    """Validates and prepares commands for execution."""

    def __init__(self, default_timeout: float = 60.0) -> None:
        self._default_timeout = default_timeout
        self._blocked_patterns = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]

    def prepare(
        self,
        request: dict[str, Any],
        user_query: str = "",
        timeout: float | None = None,
    ) -> PreparedCommand:
        """Validate a raw action request and return a prepared command."""
        action = request.get("action", "execute_command")
        shell = request.get("shell", self._default_shell())
        command = request.get("command", "").strip()
        params = request.get("params") or {}
        intent = request.get("intent") or action
        explanation = request.get("explanation", "")

        if not command:
            raise CommandBlockedError("Kein Befehl angegeben.")

        if self._is_blocked(command):
            raise CommandBlockedError(
                f"Befehl wurde aus Sicherheitsgründen blockiert: {command}"
            )

        # Content-Filter (tarno/security/content_filter.py): schließt die Lücke
        # der _BLOCKED_PATTERNS oben - Fork-Bomben und Endlosschleifen-mit-Spawn
        # (das Muster des Overload-Vorfalls vom 2026-07-15) matchen keine der
        # obigen Signaturen und kämen sonst ungehindert durch.
        content_safe, content_reason = is_output_safe(command)
        if not content_safe:
            raise CommandBlockedError(
                f"Befehl durch Content-Filter blockiert: {content_reason}"
            )

        risk_level = self.assess_risk(action, command, intent)
        if risk_level == RiskLevel.BLOCKED:
            raise CommandBlockedError(
                f"Befehl wurde aufgrund des Risikoniveaus blockiert: {command}"
            )

        return PreparedCommand(
            action=action,
            shell=shell,
            command=command,
            params=params,
            risk_level=risk_level,
            intent=str(intent),
            user_query=user_query,
            timeout=timeout if timeout is not None else self._default_timeout,
            explanation=explanation,
        )

    def assess_risk(self, action: str, command: str, intent: str) -> RiskLevel:
        """Determine the risk level of a command."""
        lower_command = command.lower()

        if any(pattern.search(lower_command) for pattern in self._blocked_patterns):
            return RiskLevel.BLOCKED

        if _targets_protected_system_path(lower_command):
            return RiskLevel.BLOCKED

        # Named intents with an explicit classification (e.g. "format_disk" ->
        # BLOCKED) take priority over the generic keyword heuristic below.
        # Without this, a command like "format C: /y" would hit the "format"
        # entry in _HIGH_RISK_KEYWORDS first and resolve to HIGH instead of
        # BLOCKED - which, combined with AutonomyMode.ULTIMATE bypassing HIGH
        # confirmations entirely, would let a destructive disk format through
        # autonomously despite being explicitly classified as BLOCKED.
        if action != "execute_command" and intent in _RISK_INTENTS:
            return _RISK_INTENTS[intent]

        for keyword in _HIGH_RISK_KEYWORDS:
            if keyword.lower() in lower_command:
                return RiskLevel.HIGH

        if action == "execute_command":
            # winget install/remove, system updates etc. are medium risk
            if any(k in lower_command for k in ("winget", "choco", "scoop", "apt", "dnf", "pacman")):
                return RiskLevel.MEDIUM
            # network diagnostics are low risk
            if any(k in lower_command for k in ("ping", "tracert", "nslookup", "ipconfig", "get-net", "test-connection")):
                return RiskLevel.LOW
            # unknown shell commands default to medium
            return RiskLevel.MEDIUM

        return _RISK_INTENTS.get(intent, RiskLevel.MEDIUM)

    def _is_blocked(self, command: str) -> bool:
        lower_command = command.lower()
        if any(pattern.search(lower_command) for pattern in self._blocked_patterns):
            return True
        return _targets_protected_system_path(lower_command)

    @staticmethod
    def _default_shell() -> str:
        import sys
        if sys.platform == "win32":
            return "powershell"
        return "bash"

    def build_result(
        self,
        prepared: PreparedCommand,
        returncode: int | None,
        stdout: str,
        stderr: str,
        error: str | None = None,
    ) -> ActionResult:
        """Create a truthful ActionResult from executor output."""
        success = error is None and returncode == 0
        message = self._format_message(prepared, success, returncode, stdout, stderr, error)
        details = {
            "command": prepared.command,
            "shell": prepared.shell,
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        return ActionResult(
            success=success,
            message=message,
            error_code="ExecutionError" if not success else None,
            details=details,
        )

    @staticmethod
    def _format_message(
        prepared: PreparedCommand,
        success: bool,
        returncode: int | None,
        stdout: str,
        stderr: str,
        error: str | None,
    ) -> str:
        if error:
            return f"Fehler bei '{prepared.intent}': {error}"
        if not success:
            reason = stderr.strip() or f"Rückgabewert {returncode}"
            return f"'{prepared.intent}' ist fehlgeschlagen: {reason}"
        output = stdout.strip()
        if output:
            return f"'{prepared.intent}' erfolgreich ausgeführt.\n{output}"
        return f"'{prepared.intent}' erfolgreich ausgeführt."
