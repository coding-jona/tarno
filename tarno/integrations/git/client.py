"""Local Git client helpers."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class GitStatus:
    branch: str
    ahead: int
    behind: int
    modified: list[str]
    untracked: list[str]


class GitClient:
    """Runs read-only and safe Git commands in a local repository."""

    def __init__(self, repo_path: Path | str = ".") -> None:
        self._repo = Path(repo_path).expanduser().resolve()

    def _run(self, *args: str, check: bool = False) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=self._repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=check,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError:
            return 127, "", "git not found"

    def status(self) -> GitStatus:
        _, branch_out, _ = self._run("rev-parse", "--abbrev-ref", "HEAD")
        branch = branch_out.strip() or "unknown"

        _, ahead_behind, _ = self._run(
            "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"
        )
        ahead = behind = 0
        if ahead_behind:
            parts = ahead_behind.strip().split("\t")
            if len(parts) == 2:
                try:
                    behind = int(parts[0])
                    ahead = int(parts[1])
                except ValueError:
                    pass

        _, status_out, _ = self._run("status", "--porcelain")
        modified: list[str] = []
        untracked: list[str] = []
        for line in status_out.splitlines():
            if len(line) < 3:
                continue
            status_code = line[:2]
            filename = line[3:]
            if status_code[1] == "?":
                untracked.append(filename)
            else:
                modified.append(filename)

        return GitStatus(
            branch=branch,
            ahead=ahead,
            behind=behind,
            modified=modified,
            untracked=untracked,
        )

    def is_repo(self) -> bool:
        return self._run("rev-parse", "--is-inside-work-tree")[0] == 0
