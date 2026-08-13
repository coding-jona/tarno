"""System information retrieval."""

from __future__ import annotations

import logging
import platform
import subprocess

log = logging.getLogger(__name__)


def get_system_info() -> str:
    lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Rechner: {platform.node()}",
        f"Prozessor: {platform.processor()}",
        f"Python: {platform.python_version()}",
    ]

    try:
        import psutil
        lines.append(f"CPU-Auslastung: {psutil.cpu_percent(interval=0.5)}%")
        mem = psutil.virtual_memory()
        lines.append(f"RAM: {mem.percent}% belegt ({mem.used // (1024**3)} / {mem.total // (1024**3)} GB)")
        # KERNFIX (Code-Review): "/" ist unter Windows KEIN fixer, universeller
        # Root wie unter POSIX - psutil.disk_usage("/") liefert das Laufwerk
        # des aktuellen Arbeitsverzeichnisses, still und OHNE das Laufwerk zu
        # nennen. Live bestaetigt: vom H:-Ordner aus lieferte das H:-Werte, vom
        # C:-Ordner aus C:-Werte - fuer "wie viel Speicherplatz habe ich noch"
        # will der Nutzer aber die SYSTEMPLATTE, unabhaengig davon, von wo aus
        # der Prozess zufaellig gestartet wurde (gerade nach einer Umstellung
        # auf ein anderes Dev-Laufwerk wie H: besonders relevant). Jetzt
        # explizit %SystemDrive% (Windows) bzw. "/" (POSIX) UND das Laufwerk
        # in der Ausgabe benannt, statt es zu verschweigen.
        import os as _os
        system_drive = _os.environ.get("SystemDrive", "C:") + "\\" if _os.name == "nt" else "/"
        disk = psutil.disk_usage(system_drive)
        lines.append(f"Festplatte ({system_drive}): {disk.percent}% belegt")
    except ImportError:
        pass

    return "\n".join(lines)


def get_cpu_ram_stats() -> tuple[str, str]:
    """Cheap, non-blocking CPU/RAM snapshot for periodic GUI refresh."""
    try:
        import psutil

        cpu = f"{psutil.cpu_percent(interval=None):.0f}%"
        mem = psutil.virtual_memory()
        ram = f"{mem.percent:.0f}% ({mem.used // (1024**3)} / {mem.total // (1024**3)} GB)"
        return cpu, ram
    except ImportError:
        return "n/a", "n/a"


def get_gpu_name() -> str:
    """One-off GPU name lookup (Windows only) — call once, not on a timer."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)",
            ],
            capture_output=True, text=True, timeout=5,
        )
        name = result.stdout.strip()
        return name or "Unbekannt"
    except Exception:
        log.warning("GPU-Name konnte nicht ermittelt werden", exc_info=True)
        return "Unbekannt"
