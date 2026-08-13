"""File system operations — open, search, copy, move, delete."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from tarno.core.workspace import (
    is_allowed,
    list_roots,
    resolve_for_read,
    resolve_for_write,
    search_all_roots,
)

log = logging.getLogger(__name__)


def _root_label(path: Path) -> str:
    try:
        return path.name or str(path)
    except Exception:
        return str(path)


def open_file(filepath: str, workspace: dict[str, Any] | None = None) -> str:
    path = resolve_for_read(filepath, workspace)
    if path is None:
        return f"Datei nicht gefunden: {filepath}"

    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

        log.info("Datei geöffnet: %s", path)
        return f"{path.name} wurde geöffnet."
    except Exception as exc:
        return f"Fehler beim Öffnen von {path.name}: {exc}"


def search_files(directory: str, pattern: str, workspace: dict[str, Any] | None = None) -> str:
    if workspace and (not directory or directory.strip() == "."):
        matches = search_all_roots("", pattern, workspace, max_results=20)
    else:
        root = resolve_for_read(directory, workspace) if workspace else Path(directory).expanduser().resolve()
        if root is None or not root.is_dir():
            return f"Verzeichnis nicht gefunden: {directory}"
        matches = list(root.rglob(pattern))[:20]

    if not matches:
        return f"Keine Dateien gefunden für '{pattern}'"

    lines = [str(m) for m in matches]
    return "\n".join(lines)


def create_directory(path: str, workspace: dict[str, Any] | None = None) -> str:
    """Create a new directory (including parents), restricted to the user's
    home directory or the active workspace (Block 5, Phase 44)."""
    target = resolve_for_write(path, workspace)
    if target is None:
        return f"Sicherheitshalber dürfen Verzeichnisse nur unter {Path.home()} oder im Workspace erstellt werden: {path}"
    target.mkdir(parents=True, exist_ok=True)
    return f"Verzeichnis erstellt: {target}"


def copy_file(source: str, destination: str, workspace: dict[str, Any] | None = None) -> str:
    """Copy a file. The destination is restricted to the user's home directory
    or the active workspace; the source may be read from anywhere OS permits."""
    src = resolve_for_read(source, workspace)
    if src is None:
        # Source may be an absolute existing path outside home/workspace.
        candidate = Path(source).expanduser().resolve()
        if candidate.exists():
            src = candidate
    if src is None:
        return f"Quelle nicht gefunden: {source}"
    dst = resolve_for_write(destination, workspace)
    if dst is None:
        return f"Sicherheitshalber darf nur nach {Path.home()} oder in den Workspace kopiert werden: {destination}"

    shutil.copy2(src, dst)
    return f"{src.name} kopiert nach {dst}"


def move_file(source: str, destination: str, workspace: dict[str, Any] | None = None) -> str:
    """Move a file. Both source and destination must be under the user's
    home directory or the active workspace - unlike copy_file, a move DELETES
    the source, so an out-of-allowed source is just as much a risk."""
    src = resolve_for_read(source, workspace)
    if src is None:
        return f"Quelle nicht gefunden: {source}"
    if not is_allowed(src, workspace):
        return f"Sicherheitshalber darf nur innerhalb von {Path.home()} oder des Workspaces verschoben werden (Quelle): {src}"
    dst = resolve_for_write(destination, workspace)
    if dst is None:
        return f"Sicherheitshalber darf nur innerhalb von {Path.home()} oder des Workspaces verschoben werden (Ziel): {destination}"

    shutil.move(str(src), str(dst))
    return f"{src.name} verschoben nach {dst}"


def delete_file(filepath: str, workspace: dict[str, Any] | None = None) -> str:
    """Delete a file, restricted to the user's home directory or the active
    workspace (Block 5, Phase 44/50)."""
    path = resolve_for_write(filepath, workspace)
    if path is None:
        return f"Sicherheitshalber dürfen Dateien nur unter {Path.home()} oder im Workspace gelöscht werden: {filepath}"
    if not path.exists():
        return f"Datei nicht gefunden: {filepath}"

    path.unlink()
    return f"{path.name} gelöscht."


def read_file(filepath: str, workspace: dict[str, Any] | None = None) -> str:
    path = resolve_for_read(filepath, workspace)
    if path is None:
        return f"Datei nicht gefunden: {filepath}"

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > 4000:
            content = content[:4000] + "\n...(abgeschnitten)"
        return content
    except Exception as exc:
        return f"Fehler beim Lesen: {exc}"


def write_file(filepath: str, content: str, workspace: dict[str, Any] | None = None) -> str:
    """Write text content to a file under the user's home directory or the active workspace."""
    path = resolve_for_write(filepath, workspace)
    if path is None:
        return f"Sicherheitshalber dürfen Dateien nur unter {Path.home()} oder im Workspace geschrieben werden: {filepath}"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        log.info("Datei geschrieben: %s", path)
        return f"Datei erstellt: {path}"
    except Exception as exc:
        return f"Fehler beim Schreiben von {path.name}: {exc}"


def list_directory(path: str, workspace: dict[str, Any] | None = None) -> str:
    """List files and directories inside a directory under the user's home or active workspace."""
    if workspace and (not path or path.strip() in (".", "")):
        roots = list_roots(workspace)
        if roots:
            lines = [f"[DIR] {name or _root_label(pth)}" for _id, name, pth in roots]
            return "\n".join(lines)

    target = resolve_for_read(path, workspace)
    if target is None or not target.is_dir():
        return f"Verzeichnis nicht gefunden: {path}"
    if not is_allowed(target, workspace):
        return f"Sicherheitshalber dürfen nur Verzeichnisse unter {Path.home()} oder im Workspace aufgelistet werden: {target}"

    try:
        entries = sorted(target.iterdir())
        lines = [f"{'[DIR]' if e.is_dir() else '[FILE]'} {e.name}" for e in entries]
        return "\n".join(lines) if lines else f"Verzeichnis ist leer: {target}"
    except Exception as exc:
        return f"Fehler beim Auflisten von {target}: {exc}"
