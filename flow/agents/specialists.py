"""Structured specialist result contracts and shared verifier rules."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from flow.agents.contracts import AgentCapability, AgentWriteProposal
from flow.models.assistant import AssistantActionType

SpecialistKind = Literal[
    "inbox_clarifier",
    "daily_planner",
    "weekly_reviewer",
    "project_health",
    "memory_curator",
]


class SpecialistResultBase(BaseModel):
    """Common fields for specialist outputs before route-specific rendering."""

    kind: SpecialistKind
    summary: str
    rationale: list[str] = Field(default_factory=list)
    write_proposals: list[AgentWriteProposal] = Field(default_factory=list)


class InboxClarification(BaseModel):
    source_item_id: str
    title: str
    classification: Literal["action", "project", "reference", "someday", "trash"]
    suggested_project_title: str | None = None
    suggested_next_action: str | None = None
    notes: str | None = None


class InboxClarifierResult(SpecialistResultBase):
    kind: Literal["inbox_clarifier"] = "inbox_clarifier"
    clarifications: list[InboxClarification]


class DailyPlanFocus(BaseModel):
    item_id: str | None = None
    title: str
    energy: Literal["low", "medium", "high"]
    reason: str


class DailyPlannerResult(SpecialistResultBase):
    kind: Literal["daily_planner"] = "daily_planner"
    focus_items: list[DailyPlanFocus]
    risks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class WeeklyReviewCandidate(BaseModel):
    item_id: str
    title: str
    issue: Literal["stale", "done_cleanup", "someday_review", "orphaned_next_action"]
    recommended_action: str


class WeeklyReviewerResult(SpecialistResultBase):
    kind: Literal["weekly_reviewer"] = "weekly_reviewer"
    cleanup_candidates: list[WeeklyReviewCandidate]


class ProjectHealthAssessment(BaseModel):
    project_id: str
    project_title: str
    status: Literal["on_track", "at_risk", "blocked", "stalled"]
    next_step: str | None = None
    blockers: list[str] = Field(default_factory=list)


class ProjectHealthResult(SpecialistResultBase):
    kind: Literal["project_health"] = "project_health"
    projects: list[ProjectHealthAssessment]
    recommendations: list[str] = Field(default_factory=list)


class MemoryCandidate(BaseModel):
    value: str
    kind: Literal["explicit_preference", "working_style", "project_preference"]
    scope: Literal["global", "project"]
    action: Literal["save", "update", "disable", "delete"]
    existing_entry_id: str | None = None
    reason: str


class MemoryCuratorResult(SpecialistResultBase):
    kind: Literal["memory_curator"] = "memory_curator"
    memory_candidates: list[MemoryCandidate]


SpecialistResult = (
    InboxClarifierResult
    | DailyPlannerResult
    | WeeklyReviewerResult
    | ProjectHealthResult
    | MemoryCuratorResult
)

SPECIALIST_RESULT_TYPES: dict[SpecialistKind, type[SpecialistResultBase]] = {
    "inbox_clarifier": InboxClarifierResult,
    "daily_planner": DailyPlannerResult,
    "weekly_reviewer": WeeklyReviewerResult,
    "project_health": ProjectHealthResult,
    "memory_curator": MemoryCuratorResult,
}

SPECIALIST_REQUIRED_CAPABILITIES: dict[SpecialistKind, AgentCapability] = {
    "inbox_clarifier": "propose_inbox_write",
    "daily_planner": "propose_planning_change",
    "weekly_reviewer": "propose_review_cleanup",
    "project_health": "propose_planning_change",
    "memory_curator": "propose_memory_write",
}

SPECIALIST_ALLOWED_ACTION_TYPES: dict[SpecialistKind, set[AssistantActionType]] = {
    "inbox_clarifier": {"create_task", "edit_task", "clean_up_inbox", "reassign_project"},
    "daily_planner": {"generate_daily_plan", "explain_daily_plan"},
    "weekly_reviewer": {
        "clean_up_inbox",
        "start_weekly_review",
        "edit_task",
        "reassign_project",
    },
    "project_health": {"edit_task", "reassign_project", "generate_daily_plan"},
    "memory_curator": {"save_memory"},
}


def validate_specialist_result(
    kind: SpecialistKind,
    payload: dict[str, object],
) -> SpecialistResultBase:
    """Validate a structured specialist payload against its explicit schema."""
    model = SPECIALIST_RESULT_TYPES[kind]
    return model.model_validate(payload)


def verify_specialist_result(
    result: SpecialistResultBase,
    *,
    capabilities: list[AgentCapability],
) -> None:
    """Enforce shared proposal capability and action-type rules per specialist."""
    if not result.write_proposals:
        return

    required_capability = SPECIALIST_REQUIRED_CAPABILITIES[result.kind]
    if required_capability not in capabilities:
        raise ValueError(
            f"{result.kind} requires capability {required_capability} for write proposals"
        )

    allowed_action_types = SPECIALIST_ALLOWED_ACTION_TYPES[result.kind]
    for proposal in result.write_proposals:
        if proposal.action_type not in allowed_action_types:
            raise ValueError(
                f"{result.kind} does not allow action_type {proposal.action_type}"
            )
