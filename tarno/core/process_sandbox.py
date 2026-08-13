"""Win32 Job Object sandboxing for spawned subprocesses (Block 5, Phase 41).

Every shell command TARNO executes gets its own Job Object with a hard OS-
level cap on total descendant processes and memory - a novel fork-bomb
pattern that slips past the regex content filter
(tarno/security/content_filter.py) is still capped here, since Windows
enforces Job Object limits regardless of what the spawned process runs.

Deliberately per-command, not app-wide: the Zero-Trust security plan
explicitly rejected a process-wide Job Object on the WinUI process itself,
since that would also cap TARNO's own ability to spawn its Python backend
child process (see App.xaml.cs's StartBackend()). This sandbox is scoped
narrowly to each individual command TARNO executes on the user's behalf.

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE means closing the job handle (done in
close(), called from ShellExecutor once the command's timeout/lifecycle
ends) terminates any processes still running in it - so nothing a command
spawned can outlive the command itself, bounding worst-case fork-bomb damage
to the command's own timeout window even if every other layer were bypassed.

There is an unavoidable small race window between spawning the process and
assigning it to the job (a few microseconds) during which the child could
launch a handful of its own children before job membership - and therefore
the hard limits - takes effect. This is accepted as a defense-in-depth
trade-off: the regex content filter and rate limiter already run before this
point and catch known patterns immediately; the Job Object's value is
against *novel* patterns, where capping growth within a few generations
still prevents runaway resource exhaustion.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_MAX_PROCESSES_PER_JOB = 20
_MAX_MEMORY_PER_JOB_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB


class ProcessSandbox:
    """Assigns a spawned process (by PID) to a fresh Win32 Job Object with
    hard process-count and memory limits. No-op on non-Windows platforms."""

    def __init__(
        self,
        max_processes: int = _MAX_PROCESSES_PER_JOB,
        max_memory_bytes: int = _MAX_MEMORY_PER_JOB_BYTES,
    ) -> None:
        self._max_processes = max_processes
        self._max_memory_bytes = max_memory_bytes
        self._job_handle = None

    @property
    def available(self) -> bool:
        return sys.platform == "win32"

    def create_and_assign(self, pid: int) -> bool:
        """Create a new Job Object with limits and assign the given PID to it.

        Returns True on success, False if unavailable/failed - callers should
        treat failure as a soft degradation (the regex content filter and
        rate limiter in ShellExecutor still apply regardless), not a reason
        to abort execution.
        """
        if not self.available:
            return False
        try:
            import win32api
            import win32con
            import win32job

            job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation
            )
            info["BasicLimitInformation"]["LimitFlags"] = (
                win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            info["BasicLimitInformation"]["ActiveProcessLimit"] = self._max_processes
            info["ProcessMemoryLimit"] = self._max_memory_bytes
            win32job.SetInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation, info
            )

            process_handle = win32api.OpenProcess(
                win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid
            )
            win32job.AssignProcessToJobObject(job, process_handle)
            self._job_handle = job
            log.debug(
                "Prozess %d in Job-Object-Sandbox (max %d Prozesse, %d MB)",
                pid, self._max_processes, self._max_memory_bytes // (1024 * 1024),
            )
            return True
        except Exception:
            log.warning(
                "Job-Object-Sandbox konnte nicht angewendet werden (PID %d) - "
                "Content-Filter/Rate-Limiter bleiben als Schutz aktiv",
                pid, exc_info=True,
            )
            return False

    def close(self) -> None:
        """Release the Job Object handle - also kills any still-running
        processes still assigned to it (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)."""
        if self._job_handle is None:
            return
        try:
            import win32api
            win32api.CloseHandle(self._job_handle)
        except Exception:
            log.debug("Job-Object-Handle konnte nicht geschlossen werden", exc_info=True)
        self._job_handle = None
