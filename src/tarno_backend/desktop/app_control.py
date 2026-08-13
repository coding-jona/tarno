"""Launch and close desktop applications."""

from __future__ import annotations

import glob
import logging
import os
import subprocess
import sys
import time

log = logging.getLogger(__name__)

_APP_CACHE: dict[str, str] | None = None
_APP_CACHE_BUILT_AT: float = 0.0
# KERNFIX (Code-Review): der Cache wurde vorher EINMALIG pro Prozesslaufzeit
# gebaut und nie wieder aktualisiert - bei TARNO als Dauerlauf-Assistent (Tage/
# Wochen ohne Neustart) waere eine waehrenddessen neu installierte Anwendung
# fuer open_application() bis zum naechsten Prozessneustart schlicht unsichtbar
# gewesen. 1h TTL ist ein vernuenftiger Kompromiss: Startmenü-Scan ist nicht
# gratis (rekursives .lnk-Globbing), aber neue Apps werden trotzdem in
# ueberschaubarer Zeit gefunden, ohne bei jedem einzelnen open_application()-
# Aufruf neu zu scannen.
_APP_CACHE_TTL_SECONDS = 3600.0


def _build_app_cache() -> dict[str, str]:
    """Scan Start Menu for .lnk shortcuts and map lowercase names to paths."""
    global _APP_CACHE, _APP_CACHE_BUILT_AT
    if _APP_CACHE is not None and (time.monotonic() - _APP_CACHE_BUILT_AT) < _APP_CACHE_TTL_SECONDS:
        return _APP_CACHE

    _APP_CACHE_BUILT_AT = time.monotonic()
    _APP_CACHE = {}
    search_dirs = []

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            search_dirs.append(os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"))
        search_dirs.append(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs")

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for lnk in glob.glob(os.path.join(d, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0].lower()
            _APP_CACHE[name] = lnk

    log.info("%d Anwendungen im Startmenü gefunden", len(_APP_CACHE))
    return _APP_CACHE


def _find_best_match(app_name: str) -> str | None:
    """Find the best matching shortcut for a given app name."""
    cache = _build_app_cache()
    query = app_name.lower().strip()

    if query in cache:
        return cache[query]

    for name, path in cache.items():
        if query in name or name in query:
            return path

    return None


def _find_uwp_app(app_name: str) -> str | None:
    """Find a UWP/Store app via PowerShell Get-StartApps."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-StartApps | Where-Object {{ $_.Name -match '{app_name}' }} "
             "| Select-Object -First 1 -ExpandProperty AppID"],
            capture_output=True, text=True, timeout=5,
        )
        app_id = result.stdout.strip()
        if app_id:
            log.info("UWP-App gefunden: %s -> %s", app_name, app_id)
            return app_id
    except Exception:
        log.debug("UWP-Suche fehlgeschlagen für %s", app_name)
    return None


def open_application(app_name: str) -> str:
    try:
        if sys.platform == "win32":
            match = _find_best_match(app_name)
            if match:
                os.startfile(match)
                log.info("Anwendung geöffnet: %s -> %s", app_name, match)
                return f"{app_name} wurde geöffnet."

            uwp_id = _find_uwp_app(app_name)
            if uwp_id:
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{uwp_id}"])
                log.info("UWP-App geöffnet: %s -> %s", app_name, uwp_id)
                return f"{app_name} wurde geöffnet."

            os.startfile(app_name)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])

        log.info("Anwendung geöffnet: %s", app_name)
        return f"{app_name} wurde geöffnet."
    except Exception as exc:
        log.warning("Konnte %s nicht öffnen: %s", app_name, exc)
        return f"Fehler beim Öffnen von {app_name}: {exc}"
