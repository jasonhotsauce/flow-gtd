"""Deterministic local adapter for tests and staged migrations."""

from __future__ import annotations

from flow.agents.contracts import AgentRequest, AgentResult, AgentTraceEvent


class DeterministicAgentAdapter:
    """Small predictable adapter used before a live SDK provider is configured."""

    name = "deterministic"

    def __init__(self, response_text: str | None = None) -> None:
        self._response_text = response_text

    def run(self, request: AgentRequest) -> AgentResult:
        response = self._response_text
        if response is None:
            inbox_count = request.context.get("inbox_count")
            memory_count = request.context.get("memory_count")
            if inbox_count is not None and memory_count is not None:
                response = (
                    "I can help capture work, summarize today's plan, or save a "
                    f"preference. Right now you have {inbox_count} inbox items and "
                    f"{memory_count} saved memories."
                )
            else:
                response = "I can help capture work, plan the day, or review your system."
        return AgentResult(
            response_text=response,
            provider=self.name,
            trace_events=[
                AgentTraceEvent(
                    stage=self.name,
                    summary="Generated deterministic agent response.",
                    provider=self.name,
                    payload={"route_hint": request.route_hint or "none"},
                )
            ],
        )
