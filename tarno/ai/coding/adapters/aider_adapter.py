"""aider.chat integration as a TARNO coding backend."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Iterator

from tarno.ai.coding.adapters.base import CodingBackend, OnOutput
from tarno.ai.coding.exceptions import (
    NoProviderConfiguredError,
    WorkspaceNotAGitRepoError,
)
from tarno.ai.coding.io_capture import TarnoInputOutput
from tarno.ai.coding.protocol import CodingOutput

log = logging.getLogger(__name__)

_PROVIDER_PREFIX = {
    "mistral": "mistral",
    "ollama": "ollama",
    "claude": "claude",
    "openai": "openai",
}


class AiderBackend(CodingBackend):
    """Runs `aider` programmatically in the active workspace."""

    name = "aider"

    def __init__(self, config, secrets=None) -> None:
        self.config = config
        self.secrets = secrets

    def _model_name(self) -> str:
        provider = self.config.coding.provider
        model = self.config.coding.model
        prefix = _PROVIDER_PREFIX.get(provider, provider)
        return f"{prefix}/{model}"

    def _api_key(self, provider: str) -> str | None:
        env_key = f"{provider.upper()}_API_KEY"
        if self.secrets is not None:
            try:
                value = self.secrets.get(f"{provider}_api_key")
                if value:
                    return value
            except Exception:
                log.warning("API-Key für %s nicht ermittelbar", provider)
        return os.environ.get(env_key)

    def _validate_git_roots(self, workspace: dict[str, Any]) -> list[str]:
        folders = workspace.get("folders", []) or []
        roots = [f.get("path", "") for f in folders if f.get("path", "")]
        if not roots and workspace.get("root_path"):
            roots = [workspace["root_path"]]
        if not roots:
            # Kein Workspace-Ordner ueberhaupt uebergeben (z.B. Agent-Pool-Lauf
            # ohne ausgewaehlten Workspace) - ohne diesen Guard gibt die
            # Funktion still eine leere Liste zurueck und der Aufrufer
            # (edit_apply.apply_merged_instruction -> AiderBackend.run)
            # crasht ungeschuetzt mit "IndexError: list index out of range"
            # bei roots[0] statt einer verstaendlichen Fehlermeldung.
            raise WorkspaceNotAGitRepoError(
                "Kein Workspace-Ordner ausgewählt oder Ordner enthält kein Git-Repository."
            )
        valid = []
        for path in roots:
            if not os.path.isdir(os.path.join(path, ".git")):
                raise WorkspaceNotAGitRepoError(
                    f"Workspace-Root '{path}' ist kein Git-Repository."
                )
            valid.append(path)
        return valid

    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        on_output: OnOutput | None = None,
    ) -> Iterator[CodingOutput]:
        try:
            from aider.coders import Coder
            from aider.models import Model
        except ImportError:
            yield CodingOutput(
                kind="error",
                text="aider ist nicht installiert. Führe 'pip install aider-chat' aus.",
            )
            return

        roots = self._validate_git_roots(workspace)
        repo_root = roots[0]
        provider = self.config.coding.provider
        api_key = self._api_key(provider)
        if api_key is None:
            raise NoProviderConfiguredError(f"Kein API-Key für {provider} konfiguriert.")

        os.environ[f"{provider.upper()}_API_KEY"] = api_key

        model = Model(self._model_name())
        io = TarnoInputOutput(on_output=on_output)

        if read_only:
            prompt = (
                f"[READ-ONLY] {prompt}\n"
                "WICHTIG: Führe keine Dateiänderungen durch. Analysiere oder beantworte nur."
            )

        max_iterations = getattr(self.config.llm, "max_coding_iterations", 0)
        if max_iterations <= 0:
            max_iterations = 10_000  # praktisch unbegrenzt, bricht über Timeout/Fertig-Check ab
        timeout = getattr(self.config.coding, "timeout", 0.0) or 0.0
        start = time.monotonic()
        continuation = (
            "Fahre mit dem nächsten konkreten Schritt fort, falls noch nötig. "
            "Wiederhole keine bereits gemeldete Zusammenfassung."
        )
        done_keywords = (
            "fertig", "erledigt", "abgeschlossen", "geschafft", "beendet",
            "done", "completed", "finished",
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(repo_root)
            coder = Coder.create(main_model=model, fnames=fnames, io=io)
            coder.run(prompt)

            if not read_only:
                for i in range(1, max_iterations):
                    if timeout and (time.monotonic() - start) > timeout:
                        break
                    yield CodingOutput(kind="system", text=f"Autonome Iteration {i + 1}...")
                    response = coder.run(continuation)
                    if not response or any(k in response.lower() for k in done_keywords):
                        break

            yield CodingOutput(kind="summary", text="Coding-Task abgeschlossen.")
        except Exception as exc:
            log.exception("aider-Fehler")
            yield CodingOutput(kind="error", text=f"Fehler bei aider: {exc}")
        finally:
            os.chdir(original_cwd)
