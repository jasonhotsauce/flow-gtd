"""Typed wrapper around the Obsidian CLI executable."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(slots=True)
class ObsidianCLIResult:
    ok: bool
    message: str | None = None
    stdout: str = ""


class ObsidianCLIError(RuntimeError):
    """Raised when an Obsidian CLI command cannot be completed."""


class ObsidianCLI:
    """Client for the `obsidian` command-line tool."""

    def __init__(self, binary: str = "obsidian") -> None:
        self._binary = binary

    def create_note(self, vault_path: str, note_path: str, content: str) -> ObsidianCLIResult:
        completed = self._run(
            [
                self._binary,
                "note",
                "create",
                "--vault",
                vault_path,
                "--file",
                note_path,
                "--content",
                content,
            ]
        )
        return ObsidianCLIResult(ok=True, stdout=completed.stdout)

    def health_check(self) -> ObsidianCLIResult:
        if shutil.which(self._binary) is None:
            return ObsidianCLIResult(ok=False, message="obsidian CLI not found")
        return ObsidianCLIResult(ok=True)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # pragma: no cover - exercised through tests
            raise ObsidianCLIError(str(exc)) from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            raise ObsidianCLIError(message)

        return completed
