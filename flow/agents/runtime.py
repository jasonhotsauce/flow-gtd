"""Provider-neutral Flow agent runtime."""

from __future__ import annotations

from pydantic import ValidationError

from flow.agents.adapters.base import AgentRuntimeAdapter
from flow.agents.contracts import (
    AgentCapability,
    AgentRequest,
    AgentResult,
    AgentTraceEvent,
)

WRITE_CAPABILITIES_BY_ACTION: dict[str, AgentCapability] = {
    "create_task": "propose_inbox_write",
    "edit_task": "propose_planning_change",
    "generate_daily_plan": "propose_planning_change",
    "clean_up_inbox": "propose_review_cleanup",
    "start_weekly_review": "propose_review_cleanup",
    "change_reminder": "propose_planning_change",
    "reassign_project": "propose_planning_change",
    "save_memory": "propose_memory_write",
}


class AgentRuntime:
    """Run Flow agent requests through a configured adapter with safe guards."""

    def __init__(self, adapter: AgentRuntimeAdapter) -> None:
        self._adapter = adapter

    @property
    def provider_name(self) -> str:
        return self._adapter.name

    def run(self, request: AgentRequest) -> AgentResult:
        start_event = AgentTraceEvent(
            stage="runtime",
            summary="Started Flow agent runtime request.",
            provider=self.provider_name,
            payload={"route_hint": request.route_hint or "none"},
        )
        try:
            raw_result = self._adapter.run(request)
            result = AgentResult.model_validate(raw_result.model_dump())
            if not self._write_proposals_allowed(request, result):
                return self._safe_failure(
                    provider=self.provider_name,
                    trace_events=[
                        start_event,
                        AgentTraceEvent(
                            stage="runtime_verifier",
                            summary=(
                                "Rejected agent write proposal outside requested "
                                "capabilities."
                            ),
                            provider=self.provider_name,
                        ),
                    ],
                )
            result.trace_events = [start_event, *result.trace_events]
            return result
        except ValidationError:
            return self._safe_failure(
                provider=self.provider_name,
                trace_events=[
                    start_event,
                    AgentTraceEvent(
                        stage="runtime_verifier",
                        summary="Rejected unsafe agent runtime output.",
                        provider=self.provider_name,
                    ),
                ],
            )
        except Exception:
            return self._safe_failure(
                provider=self.provider_name,
                trace_events=[
                    start_event,
                    AgentTraceEvent(
                        stage="runtime",
                        summary="Agent runtime adapter failed safely.",
                        provider=self.provider_name,
                    ),
                ],
            )

    def _safe_failure(
        self, *, provider: str, trace_events: list[AgentTraceEvent]
    ) -> AgentResult:
        return AgentResult(
            response_text="",
            provider=provider,
            failed=True,
            trace_events=trace_events,
        )

    def _write_proposals_allowed(
        self, request: AgentRequest, result: AgentResult
    ) -> bool:
        requested = set(request.capabilities)
        for proposal in result.write_proposals:
            required = WRITE_CAPABILITIES_BY_ACTION.get(proposal.action_type)
            if required is None or required not in requested:
                return False
        return True
