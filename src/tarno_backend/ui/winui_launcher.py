"""Orchestrate the WinUI 3 frontend and the Python gRPC backend.

This module is used by `tarno/__main__.py` when `ui.backend` is set to
"winui". It starts the Python backend, waits until the gRPC port is reachable,
launches the pre-built WinUI .exe, and ensures both processes are terminated
when TARNO exits.
"""

from __future__ import annotations

import atexit
import logging
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tarno_backend.core.config import TarnoConfig

log = logging.getLogger(__name__)


def _project_root() -> Path:
    """Return the repository root from this module's location.

    Deliberately NOT tarno_backend.utils.paths.find_repo_root(): this module
    is also the production launch path inside the PyInstaller bundle, which
    has no .git/ or src/ marker to search for.
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def _default_exe_path() -> Path:
    """Return the default path to the built WinUI .exe."""
    return (
        _project_root()
        / "src"
        / "TARNO.UI"
        / "bin"
        / "x64"
        / "Debug"
        / "net8.0-windows10.0.19041.0"
        / "TARNO.UI.exe"
    )


def _is_port_open(host: str, port: int) -> bool:
    """Check whether a TCP port accepts connections."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_backend(host: str, port: int, timeout_seconds: int) -> bool:
    """Poll the gRPC port until it is reachable or the timeout expires."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _is_port_open(host, port):
            return True
        time.sleep(0.25)
    return False


class WinUILauncher:
    """Launch and supervise the WinUI frontend and its gRPC backend."""

    def __init__(self, config: TarnoConfig) -> None:
        self._config = config
        self._backend: subprocess.Popen[Any] | None = None
        self._frontend: subprocess.Popen[Any] | None = None

    def _exe_path(self) -> Path:
        """Return the configured or default WinUI exe path."""
        configured = self._config.ui.winui.exe_path
        if configured:
            return Path(configured).expanduser()
        return _default_exe_path()

    def _start_backend(self) -> subprocess.Popen[Any]:
        """Start the Python gRPC backend subprocess."""
        root = _project_root()
        backend_script = root / "start_tarno_winui_backend.py"
        if not backend_script.exists():
            raise FileNotFoundError(f"Backend-Skript nicht gefunden: {backend_script}")

        cmd = [
            sys.executable,
            str(backend_script),
            "--port",
            str(self._config.ui.winui.backend_port),
        ]
        log.info("Starte WinUI-Backend: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._backend = proc
        return proc

    def _start_frontend(self, exe_path: Path) -> subprocess.Popen[Any]:
        """Start the WinUI .exe subprocess."""
        log.info("Starte WinUI-Frontend: %s", exe_path)
        proc = subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._frontend = proc
        return proc

    def _terminate(self) -> None:
        """Terminate both child processes on exit."""
        for name, proc in [("Frontend", self._frontend), ("Backend", self._backend)]:
            if proc is None or proc.poll() is not None:
                continue
            log.info("Beende %s (PID %d)", name, proc.pid)
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    log.warning("%s reagiert nicht, force-kill", name)
                    proc.kill()
                    proc.wait(timeout=2)
            except Exception:
                log.exception("Fehler beim Beenden von %s", name)

    def _register_cleanup(self) -> None:
        """Register atexit and signal handlers for clean shutdown."""
        atexit.register(self._terminate)

        def _signal_handler(signum: int, _frame: Any) -> None:
            log.info("Signal %d empfangen — beende WinUI-Launcher", signum)
            self._terminate()
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, _signal_handler)  # type: ignore[attr-defined]

    def run(self) -> int:
        """Start backend and frontend, then block until the frontend exits."""
        self._register_cleanup()

        exe_path = self._exe_path()
        if not exe_path.exists():
            log.error("WinUI-Exe nicht gefunden: %s", exe_path)
            log.error("Bitte zuerst bauen: dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64")
            log.error("Oder --legacy-ui verwenden.")
            return 1

        backend = self._start_backend()
        port = self._config.ui.winui.backend_port
        wait_seconds = self._config.ui.winui.backend_wait_seconds

        if not _wait_for_backend("localhost", port, wait_seconds):
            log.error("Backend nicht nach %d Sekunden erreichbar (Port %d)", wait_seconds, port)
            self._terminate()
            return 1

        log.info("Backend erreichbar auf Port %d", port)
        frontend = self._start_frontend(exe_path)

        try:
            frontend.wait()
        except KeyboardInterrupt:
            log.info("Tastatur-Unterbrechung — beende")
            self._terminate()
            return 0

        backend_return = backend.poll()
        if backend_return is None:
            log.warning("Backend läuft noch nach Frontend-Exit — beende")
            self._terminate()
        else:
            log.info("Frontend beendet (Code %d)", frontend.returncode)

        return frontend.returncode


def launch_winui(config: TarnoConfig | None = None) -> int:
    """Convenience entry point used by `tarno/__main__.py`."""
    config = config or TarnoConfig.load()
    return WinUILauncher(config).run()
