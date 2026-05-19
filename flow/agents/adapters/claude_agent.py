"""Claude Agent SDK adapter shell."""

from __future__ import annotations

from flow.agents.contracts import AgentRequest, AgentResult


class ClaudeAgentSDKAdapter:
    """Adapter boundary for Claude Agent SDK backed product/dev agents."""

    name = "claude-agent"

    def __init__(self, *, model: str = "", timeout: float = 60.0) -> None:
        self.model = model
        self.timeout = timeout

    def run(self, request: AgentRequest) -> AgentResult:
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "claude-agent runtime is not installed; install the optional "
                "Claude Agent SDK dependency before enabling this provider."
            ) from exc
        raise NotImplementedError("Claude Agent SDK adapter is staged for Phase 4")
