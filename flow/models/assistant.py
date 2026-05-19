"""Assistant domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AssistantActionType = Literal[
    "create_task",
    "edit_task",
    "generate_daily_plan",
    "explain_daily_plan",
    "clean_up_inbox",
    "start_weekly_review",
    "change_reminder",
    "reassign_project",
    "save_memory",
]
AssistantProposalStatus = Literal["none", "pending", "confirmed", "dismissed"]
AssistantAuditStatus = Literal["ok", "warn", "blocked"]
AssistantVerificationStatus = Literal["pass", "warn", "block"]


class AssistantAgentContract(BaseModel):
    """Shared multi-agent proposal contract persisted with assistant actions."""

    request_id: str
    action_type: AssistantActionType
    target_entity_ids: list[str]
    target_entity_versions: dict[str, str]
    input_summary: str
    proposed_changes: list[str]
    field_deltas: dict[str, Any]
    preview_text: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool
    verification_status: AssistantVerificationStatus

    @model_validator(mode="after")
    def require_confirmation_for_risky_outputs(self) -> "AssistantAgentContract":
        """Enforce PRD confirmation gates for low-confidence or warned proposals."""
        if self.confidence < 0.9 and not self.requires_confirmation:
            raise ValueError("Low-confidence assistant proposals require confirmation")
        if self.verification_status != "pass" and not self.requires_confirmation:
            raise ValueError("Warned or blocked assistant proposals require confirmation")
        return self


class AssistantProposal(BaseModel):
    """A bounded assistant action that may require user confirmation."""

    action_type: AssistantActionType
    title: str
    detail: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False

    @model_validator(mode="after")
    def validate_embedded_agent_contract(self) -> "AssistantProposal":
        """Validate the explicit agent contract when one is attached."""
        raw_contract = self.payload.get("agent_contract")
        if raw_contract is None:
            return self
        contract = AssistantAgentContract.model_validate(raw_contract)
        if contract.action_type != self.action_type:
            raise ValueError("Assistant proposal action_type must match agent contract")
        if contract.requires_confirmation != self.requires_confirmation:
            raise ValueError(
                "Assistant proposal confirmation flag must match agent contract"
            )
        return self


class AssistantAuditStep(BaseModel):
    """A single assistant-orchestration stage."""

    stage: str
    status: AssistantAuditStatus = "ok"
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssistantTurn(BaseModel):
    """A persisted assistant turn plus any audit metadata."""

    id: str
    prompt: str
    response: str
    route: str
    proposal: AssistantProposal | None = None
    proposal_status: AssistantProposalStatus = "none"
    audit_steps: list[AssistantAuditStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
