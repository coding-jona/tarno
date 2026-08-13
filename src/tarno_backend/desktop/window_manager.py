"""Window/process enumeration and control via the Win32 API (pywin32)."""

from __future__ import annotations

import logging

import win32con
import win32gui
import win32process

from tarno_backend.core.action_result import ActionResult

log = logging.getLogger(__name__)

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


def _process_name(pid: int) -> str:
    if psutil is None:
        return ""
    try:
        return psutil.Process(pid).name()
    except Exception:
        return ""


def _enum_visible_windows() -> list[dict[str, object]]:
    """Enumerate top-level windows that have a title and are visible."""
    windows: list[dict[str, object]] = []

    def _callback(hwnd: int, _extra: object) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "process": _process_name(pid),
        })

    win32gui.EnumWindows(_callback, None)
    return windows


def list_windows() -> list[dict[str, object]]:
    """Return all visible top-level windows (title, process name, PID)."""
    try:
        return _enum_visible_windows()
    except Exception:
        log.exception("Fenster-Auflistung fehlgeschlagen")
        return []


def get_active_window() -> dict[str, object] | None:
    """Return info about the currently foreground window, or None."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return {"hwnd": hwnd, "title": title, "pid": pid, "process": _process_name(pid)}
    except Exception:
        log.exception("Aktives Fenster konnte nicht ermittelt werden")
        return None


def _find_window_by_title(title_substring: str) -> int | None:
    needle = title_substring.lower()
    for window in _enum_visible_windows():
        if needle in str(window["title"]).lower():
            return int(window["hwnd"])
    return None


def focus_window(title_substring: str) -> ActionResult:
    """Bring the first window whose title contains *title_substring* to the foreground."""
    try:
        hwnd = _find_window_by_title(title_substring)
    except Exception as exc:
        return ActionResult.from_exception(exc, f"Fenstersuche fehlgeschlagen: {exc}")

    if hwnd is None:
        return ActionResult(
            success=False,
            message=f"Kein Fenster mit Titel '{title_substring}' gefunden.",
            error_code="WindowNotFound",
        )

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        title = win32gui.GetWindowText(hwnd)
        log.info("Fenster fokussiert: %s", title)
        return ActionResult(success=True, message=f"Fenster '{title}' fokussiert.")
    except Exception as exc:
        return ActionResult.from_exception(exc, f"Fokussieren fehlgeschlagen: {exc}")


def close_window(title_substring: str) -> ActionResult:
    """Politely close the first window whose title contains *title_substring*.

    Uses WM_CLOSE (lets the application handle its own shutdown/save prompts)
    rather than TerminateProcess, which would kill it without cleanup.
    """
    try:
        hwnd = _find_window_by_title(title_substring)
    except Exception as exc:
        return ActionResult.from_exception(exc, f"Fenstersuche fehlgeschlagen: {exc}")

    if hwnd is None:
        return ActionResult(
            success=False,
            message=f"Kein Fenster mit Titel '{title_substring}' gefunden.",
            error_code="WindowNotFound",
        )

    try:
        title = win32gui.GetWindowText(hwnd)
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        log.info("Schließen-Signal an Fenster gesendet: %s", title)
        return ActionResult(success=True, message=f"Fenster '{title}' wird geschlossen.")
    except Exception as exc:
        return ActionResult.from_exception(exc, f"Schließen fehlgeschlagen: {exc}")
