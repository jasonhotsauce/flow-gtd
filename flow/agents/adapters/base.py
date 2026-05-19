"""Base protocol for Flow agent runtime adapters."""

from __future__ import annotations

from typing import Protocol

from flow.agents.contracts import AgentRequest, AgentResult


class AgentRuntimeAdapter(Protocol):
    """Provider adapter boundary for Flow's product agent runtime."""

    @property
    def name(self) -> str:
        """Provider name for trace and diagnostics."""
        ...

    def run(self, request: AgentRequest) -> AgentResult:
        """Run an agent request and return a normalized result."""
        ...
