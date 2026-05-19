"""Codex CLI adapter shell for future coding-agent workflows."""

from __future__ import annotations

import shutil

from flow.agents.contracts import AgentRequest, AgentResult


class CodexCLIAdapter:
    """Adapter boundary for headless Codex CLI execution."""

    name = "codex-cli"

    def __init__(self, *, model: str = "", timeout: float = 60.0) -> None:
        self.model = model
        self.timeout = timeout

    def run(self, request: AgentRequest) -> AgentResult:
        if shutil.which("codex") is None:
            raise RuntimeError(
                "codex-cli runtime is not available; install Codex CLI before "
                "enabling this provider."
            )
        raise NotImplementedError("Codex CLI adapter is staged for Phase 4")
