"""Directory/workspace ingestion into the TARNO knowledge base."""

from __future__ import annotations

import logging
from pathlib import Path

from tarno_backend.memory.knowledge_base import KnowledgeBase

log = logging.getLogger(__name__)


def _should_include(path: Path, include_patterns: list[str], exclude_patterns: list[str]) -> bool:
    """Best-effort include/exclude filter using glob-style extensions."""
    name = path.name
    suffix = path.suffix.lower()

    if include_patterns:
        if not any(name.endswith(pat) if pat.startswith("*") or not pat.startswith("*") else name == pat for pat in include_patterns):
            return False

    if exclude_patterns:
        for pat in exclude_patterns:
            if name == pat or path.match(pat):
                return False
            if suffix and pat == f"*{suffix}":
                return False
    return True


def ingest_directory(
    kb: KnowledgeBase,
    root: Path | str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> int:
    """Recursively ingest text files from *root* and return total chunk count."""
    root = Path(root).resolve()
    if not root.exists():
        log.warning("KB-Ingest: Verzeichnis nicht gefunden: %s", root)
        return 0

    includes = include_patterns or []
    excludes = exclude_patterns or [".git", "__pycache__", "node_modules", ".venv", "venv", "bin", "obj", ".vs"]
    total = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in kb._TEXT_EXTENSIONS:
            continue
        if not _should_include(path, includes, excludes):
            continue
        total += kb.ingest_file(path, chunk_size=chunk_size, overlap=overlap)

    log.info("KB-Ingest: %d Chunks aus %s", total, root)
    return total


def ingest_workspace(kb: KnowledgeBase, workspace: dict[str, object] | None, *, chunk_size: int = 1000, overlap: int = 100) -> int:
    """Ingest all folders of a workspace dict as returned by the gRPC bridge."""
    if not workspace:
        return 0
    folders = workspace.get("folders", [])
    if not folders:
        legacy_root = workspace.get("root_path", "")
        folders = [{"path": legacy_root}] if legacy_root else []
    excludes = list(workspace.get("exclude_patterns", [])) or None
    includes = list(workspace.get("include_patterns", [])) or None
    total = 0
    for folder in folders:
        path = folder.get("path")
        if path:
            total += ingest_directory(kb, path, include_patterns=includes, exclude_patterns=excludes, chunk_size=chunk_size, overlap=overlap)
    return total
