"""Multi-root workspace utilities for path resolution and sandbox checks."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _home_dir() -> Path:
    return Path.home().resolve()


def get_workspace_roots(workspace: dict[str, Any] | None) -> list[Path]:
    """Return resolved Path objects for all workspace folder roots."""
    if workspace is None:
        return []
    roots = workspace.get("root_paths") or []
    if not roots:
        legacy = workspace.get("root_path")
        if legacy:
            roots = [legacy]
    resolved: list[Path] = []
    for r in roots:
        if r:
            try:
                resolved.append(Path(r).expanduser().resolve())
            except OSError as exc:
                log.warning("Workspace-Root konnte nicht aufgeloest werden: %s (%s)", r, exc)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in resolved:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def is_allowed(path: Path, workspace: dict[str, Any] | None) -> bool:
    """Return True if the resolved path is inside the user's home directory
    or inside any workspace root."""
    resolved = path.resolve() if path.exists() else path.expanduser().absolute()
    try:
        if resolved.is_relative_to(_home_dir()):
            return True
    except ValueError:
        pass
    for root in get_workspace_roots(workspace):
        try:
            if resolved.is_relative_to(root):
                return True
        except ValueError:
            pass
    return False


def _matches_any(path: Path, patterns: list[str]) -> bool:
    if not patterns:
        return False
    # Match against the relative path within the workspace root or the file name.
    rel = path.as_posix()
    name = path.name
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        # Also support directory-style patterns like "bin/" by matching any segment.
        for part in path.parts:
            if fnmatch.fnmatch(part, pattern.rstrip('/')):
                return True
    return False


def is_excluded(path: Path, workspace: dict[str, Any] | None) -> bool:
    """Return True if the path matches an exclude pattern."""
    if workspace is None:
        return False
    return _matches_any(path, workspace.get("exclude_patterns", []))


def _sort_roots_by_length(roots: list[Path]) -> list[Path]:
    """Sort roots by path length descending so the most specific root is tried first."""
    return sorted(roots, key=lambda p: len(p.parts), reverse=True)


def resolve_for_read(raw: str, workspace: dict[str, Any] | None) -> Path | None:
    """Resolve a user-provided path for reading.

    - Absolute paths are returned if allowed.
    - Relative paths are tried against every workspace root (longest first),
      returning the first existing match.
    - Returns None if the path does not exist or is not allowed.
    """
    path = Path(raw).expanduser()
    if path.is_absolute():
        if not path.exists() or not is_allowed(path, workspace):
            return None
        return path

    roots = _sort_roots_by_length(get_workspace_roots(workspace))
    if not roots:
        # Fall back to current working directory (legacy behavior).
        candidate = path.resolve()
        return candidate if candidate.exists() else None

    for root in roots:
        candidate = (root / path).resolve()
        if candidate.exists() and is_allowed(candidate, workspace):
            return candidate
    return None


def resolve_for_write(raw: str, workspace: dict[str, Any] | None) -> Path | None:
    """Resolve a user-provided path for writing.

    - Absolute paths are returned if allowed.
    - Relative paths are resolved to the most specific matching root.
      Longest-prefix selection: if a parent directory of the target exists in
      one of the roots, that root is used. Otherwise the first root is used.
    - Returns None if the resolved path is not allowed.
    """
    path = Path(raw).expanduser()
    if path.is_absolute():
        if not is_allowed(path, workspace):
            return None
        return path

    roots = _sort_roots_by_length(get_workspace_roots(workspace))
    if not roots:
        # Legacy fallback: write relative to current directory.
        candidate = path.resolve()
        return candidate if is_allowed(candidate, workspace) else None

    best_root = roots[0]
    best_depth = -1
    for root in roots:
        candidate = root / path
        # Determine how many leading parts of the relative path already exist under this root.
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        existing_parts = 0
        checked = root
        for part in relative.parts:
            next_checked = checked / part
            if next_checked.exists():
                existing_parts += 1
                checked = next_checked
            else:
                break
        if existing_parts > best_depth:
            best_depth = existing_parts
            best_root = root

    candidate = (best_root / path).resolve()
    if not is_allowed(candidate, workspace):
        return None
    return candidate


def list_roots(workspace: dict[str, Any] | None) -> list[tuple[str, str, Path]]:
    """Return (id, name, resolved_path) tuples for all workspace roots."""
    if workspace is None:
        return []
    folders = workspace.get("folders", [])
    result: list[tuple[str, str, Path]] = []
    if not folders:
        legacy = workspace.get("root_path")
        if legacy:
            result.append(("", "", Path(legacy).expanduser().resolve()))
        return result
    for f in folders:
        path = Path(f.get("path", "")).expanduser().resolve()
        result.append((f.get("id", ""), f.get("name", ""), path))
    return result


def search_all_roots(directory: str, pattern: str, workspace: dict[str, Any] | None, max_results: int = 20) -> list[Path]:
    """Search for files matching *pattern* across all workspace roots.

    If *directory* is empty or '.', search every root. Otherwise search the
    resolved directory within each applicable root.
    """
    roots = get_workspace_roots(workspace)
    results: list[Path] = []
    directory = directory.strip() if directory else ""
    for root in roots:
        base = root if not directory or directory == "." else (root / directory).resolve()
        if not base.is_dir():
            continue
        for item in base.rglob(pattern):
            if item.is_file() and not is_excluded(item, workspace):
                results.append(item)
                if len(results) >= max_results:
                    return results
    return results
