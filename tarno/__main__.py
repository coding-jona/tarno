"""Entry point for `python -m tarno`."""

import os
import sys
from pathlib import Path


def _ensure_xdg_environment() -> None:
    """Point XDG base directories to the persistent TARNO home.

    This must run before any OVOS module is imported, because ovos_config caches
    the XDG locations at import time. In both source and bundled runs we use
    ~/.tarno (or TARNO_HOME) so that user data, config and cache never leak
    into the project/source tree.
    """
    home = Path(os.environ.get("TARNO_HOME", Path.home() / ".tarno"))

    os.environ.setdefault("XDG_CONFIG_HOME", str(home / "config"))
    os.environ.setdefault("XDG_CACHE_HOME", str(home / ".cache"))
    os.environ.setdefault("XDG_DATA_HOME", str(home / ".data"))


# Set XDG paths as early as possible.
_ensure_xdg_environment()

from tarno.core.config import TarnoConfig
from tarno.utils.log import setup_logging


def _fix_windows_encoding() -> None:
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _install_local_crash_handler(config: TarnoConfig) -> None:
    """Log uncaught exceptions locally if crash reporting is enabled.

    This handler never sends data over the network; it only appends the
    traceback to the configured log file for debugging.
    """
    if not config.telemetry.crash_reporting:
        return

    def _excepthook(exc_type, exc_value, tb):  # type: ignore[no-untyped-def]
        logging.getLogger(__name__).exception(
            "Unbehandelte Ausnahme", exc_info=(exc_type, exc_value, tb)
        )
        sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = _excepthook


def _ensure_headless_std_streams() -> None:
    """Stellt sicher, dass sys.stdin/stdout/stderr in einem
    headless/windowed Build (PyInstaller console=False) niemals None sind.

    Drittbibliotheken wie aider greifen auf .encoding / .isatty() zu und
    crashen, wenn Python im headless Windows-Build die Standardstreams als
    None gesetzt hat (Live-Fund: Agent-Pool-Lauf bricht mit
    'NoneType' object has no attribute 'encoding' ab).
    """
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r", encoding="utf-8", errors="replace")
        sys.stdin.isatty = lambda: False  # type: ignore[method-assign]
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
        sys.stdout.isatty = lambda: False  # type: ignore[method-assign]
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
        sys.stderr.isatty = lambda: False  # type: ignore[method-assign]


def _ensure_console() -> None:
    """Attach to a parent console or allocate one in a windowed build."""
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    attached = bool(kernel32.AttachConsole(-1))
    if not attached:
        attached = bool(kernel32.AllocConsole())
    if attached:
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # type: ignore[assignment]
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # type: ignore[assignment]


def main() -> None:
    _ensure_headless_std_streams()
    _fix_windows_encoding()
    if "--first-start" in sys.argv:
        from tarno.first_start import run_first_start
        return run_first_start()

    config = TarnoConfig.load()

    log_file = Path.home() / ".tarno" / "logs" / "tarno.log"
    setup_logging(
        config.log_level,
        log_file=log_file,
        redact_pii=config.security.pii_redaction_enabled,
    )
    _install_local_crash_handler(config)

    if "--backend" in sys.argv:
        # Headless gRPC-backend-only mode: used by the packaged tarno.exe
        # when launched *by* the WinUI frontend (src/TARNO.UI/App.xaml.cs's
        # StartBackend()) rather than launching the frontend itself - the
        # inverse of the default (no-args) dev flow below, which has TARNO
        # (Python) launch the WinUI exe. Mirrors start_tarno_winui_backend.py.
        import asyncio
        from tarno.grpc.server import run_grpc_server

        port = config.ui.winui.backend_port
        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        mock = "--mock" in sys.argv
        try:
            asyncio.run(run_grpc_server(config=config, port=port, mock=mock))
        except KeyboardInterrupt:
            pass
    elif "--text" in sys.argv:
        _ensure_console()
        _fix_windows_encoding()
        from tarno.core.engine import TarnoEngine
        engine = TarnoEngine(config, text_mode=True)
        engine.run_text_mode()
    elif "--voice" in sys.argv or "--console" in sys.argv:
        _fix_windows_encoding()
        from tarno.core.engine import TarnoEngine
        engine = TarnoEngine(config, text_mode=False)
        engine.run()
    elif "--no-gui" in sys.argv:
        _fix_windows_encoding()
        try:
            from tarno.core.ovos_engine import TarnoOvosEngine
        except ImportError as exc:
            print(
                "Der --no-gui Modus benötigt den OpenVoiceOS-Stack, der nicht "
                "standardmäßig installiert ist (ADR-002).\n"
                "Installiere ihn mit:\n"
                "    pip install -r requirements-ovos.txt\n"
                f"\nFehlendes Paket: {exc.name or exc}"
            )
            sys.exit(1)
        engine = TarnoOvosEngine()
        engine.run()
    elif "--legacy-ui" in sys.argv or config.ui.backend == "pyside6-legacy":
        from tarno.ui.app import run_ui
        run_ui(config)
    else:
        from tarno.ui.winui_launcher import launch_winui
        return launch_winui(config)


if __name__ == "__main__":
    main()
