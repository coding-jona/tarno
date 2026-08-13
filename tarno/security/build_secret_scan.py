"""Build-time secret-leak scanning.

Extracted from the (now deprecated, see `_deprecated_legacy_installers/`)
PySide6 installer payload builder — this scan itself is generic build
tooling, not tied to that installer, and is exercised by
`tests/test_security.py`.
"""

from __future__ import annotations

import re
from pathlib import Path


def verify_no_secrets(root: Path) -> None:
    """Abort the build if any real secret is found in the bundled files.

    Scans text files for common secret patterns (API key assignments, JSON key
    fields, and Mistral-style tokens). Placeholder values are allowed.
    """
    secret_vars = [
        "MISTRAL_API_KEY",
        "PICOVOICE_API_KEY",
        "CLAUDE_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
    ]
    placeholder_re = re.compile(r"^<.*>$|^(YOUR|PLACEHOLDER|EXAMPLE|TODO|FIXME)|^\[REDACTED", re.IGNORECASE)
    secret_var_re = re.compile(
        r"(" + "|".join(re.escape(v) for v in secret_vars) + r")\s*[:=]\s*[\"']([^\"']+)[\"']"
    )
    json_key_re = re.compile(r'"key"\s*:\s*"([^"]+)"')
    mistral_token_re = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")

    text_extensions = {
        ".py", ".json", ".yaml", ".yml", ".md", ".txt", ".conf", ".cfg", ".ini", ".toml"
    }
    skip_dirs = {
        "__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build",
        # Dead/legacy code, never bundled into a real build - also contains an
        # older copy of this very scanner whose own error-message template
        # ("key": "{value}") otherwise false-positives against itself.
        "_deprecated_legacy_installers",
        # Claude Code's own state dir, including any leftover git worktrees
        # from prior agent runs (isolation:"worktree") - those are full repo
        # checkouts that carry their own copy of this same scanner file, so
        # they hit the exact same self-referential false positive described
        # above. Never part of a real build regardless.
        ".claude",
    }
    skip_files = {Path(__file__).resolve()}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() in skip_files:
            continue
        if path.suffix.lower() not in text_extensions:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for match in secret_var_re.finditer(content):
            value = match.group(2)
            if value.strip() and not placeholder_re.match(value):
                raise RuntimeError(
                    f"SECURITY CHECK FAILED: potential secret in {path}: "
                    f"{match.group(1)}={value}"
                )

        for match in json_key_re.finditer(content):
            value = match.group(1)
            if value.strip() and not placeholder_re.match(value):
                raise RuntimeError(
                    f"SECURITY CHECK FAILED: potential API key in {path}: "
                    f'"key": "{value}"'
                )

        for match in mistral_token_re.finditer(content):
            raise RuntimeError(
                f"SECURITY CHECK FAILED: potential Mistral-style token in {path}: "
                f"{match.group(0)}"
            )
