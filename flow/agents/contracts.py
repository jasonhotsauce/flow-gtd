"""Stable Flow contracts for product assistant agent runtimes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from flow.models.assistant import (
    AssistantActionType,
    AssistantProposal,
    AssistantVerificationStatus,
)

AgentCapability = Literal[
    "read_gtd_context",
    "propose_inbox_write",
    "propose_memory_write",
    "propose_planning_change",
    "propose_review_cleanup",
    "execute_tool",
    "access_coding_workspace",
]

SENSITIVE_TRACE_KEYS = {"raw_prompt", "prompt", "messages", "message", "tool_args"}


class AgentRequest(BaseModel):
    """A provider-neutral request sent to a Flow agent runtime."""

    prompt: str
    route_hint: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[AgentCapability] = Field(
        default_factory=lambda: ["read_gtd_context"]
    )
    output_mode: Literal["text", "json", "proposal"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTraceEvent(BaseModel):
    """Provider-neutral trace event safe to persist as assistant audit metadata."""

    stage: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    provider: str = "flow"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def remove_raw_prompt_payload(self) -> "AgentTraceEvent":
        """Prevent accidental persistence of prompt-like provider payloads."""
        self.payload = _sanitize_trace_payload(self.payload)
        return self


class AgentWriteProposal(BaseModel):
    """A write-capable agent output that must become an assistant proposal."""

    action_type: AssistantActionType
    title: str
    detail: str
    input_summary: str
    proposed_changes: list[str]
    field_deltas: dict[str, Any]
    preview_text: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool
    verification_status: AssistantVerificationStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    target_entity_ids: list[str] = Field(default_factory=list)
    target_entity_versions: dict[str, str] = Field(default_factory=dict)

    def to_agent_contract_payload(self, *, request_id: str) -> dict[str, Any]:
        """Return a payload compatible with `AssistantAgentContract`."""
        return {
            "request_id": request_id,
            "action_type": self.action_type,
            "target_entity_ids": self.target_entity_ids,
            "target_entity_versions": self.target_entity_versions,
            "input_summary": self.input_summary,
            "proposed_changes": self.proposed_changes,
            "field_deltas": self.field_deltas,
            "preview_text": self.preview_text,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "requires_confirmation": self.requires_confirmation,
            "verification_status": self.verification_status,
        }

    def to_assistant_proposal(self, *, request_id: str) -> AssistantProposal:
        """Convert a runtime write proposal into the persisted assistant proposal shape."""
        payload = dict(self.payload)
        payload["agent_contract"] = self.to_agent_contract_payload(request_id=request_id)
        return AssistantProposal(
            action_type=self.action_type,
            title=self.title,
            detail=self.detail,
            payload=payload,
            requires_confirmation=self.requires_confirmation,
        )


class AgentResult(BaseModel):
    """Normalized output from a Flow agent runtime adapter."""

    response_text: str
    structured_output: dict[str, Any] | None = None
    write_proposals: list[AgentWriteProposal] = Field(default_factory=list)
    trace_events: list[AgentTraceEvent] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    provider: str = "flow"
    model: str | None = None
    failed: bool = False

    @model_validator(mode="after")
    def require_confirmation_for_write_proposals(self) -> "AgentResult":
        """Keep runtime writes behind the existing assistant confirmation gate."""
        for proposal in self.write_proposals:
            if not proposal.requires_confirmation:
                raise ValueError("Agent write_proposals require requires_confirmation")
        return self


def _sanitize_trace_payload(value: Any) -> Any:
    """Recursively strip prompt-like keys from trace payloads."""
    if isinstance(value, dict):
        return {
            key: _sanitize_trace_payload(nested)
            for key, nested in value.items()
            if key not in SENSITIVE_TRACE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_trace_payload(item) for item in value]
    return value
