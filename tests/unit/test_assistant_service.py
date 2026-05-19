"""Unit tests for assistant orchestration and memory persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from flow.agents import AgentRequest, AgentResult, AgentTraceEvent
from flow.agents.runtime import AgentRuntime
from pydantic import ValidationError

from flow.core.engine import Engine
from flow.core.focus import CalendarAvailability
from flow.models import AssistantAgentContract, AssistantProposal, AssistantTurn
from flow.models import Item


@pytest.fixture
def engine(temp_db_path: Path) -> Engine:
    """Engine with temp DB."""
    return Engine(db_path=temp_db_path)


def test_assistant_capture_turn_requires_confirmation_and_records_audit(
    engine: Engine,
) -> None:
    """Capture-like prompts should produce a pending proposal before mutating data."""
    turn = engine.send_assistant_prompt("Remind me to review the launch checklist")

    assert turn.route == "capture"
    assert turn.proposal is not None
    assert turn.proposal.action_type == "create_task"
    assert turn.proposal.requires_confirmation is True
    contract = AssistantAgentContract.model_validate(
        turn.proposal.payload["agent_contract"]
    )
    assert contract.request_id == turn.id
    assert contract.action_type == "create_task"
    assert contract.target_entity_ids == []
    assert contract.target_entity_versions == {}
    assert contract.input_summary == "Remind me to review the launch checklist"
    assert contract.proposed_changes == ["Create inbox item"]
    assert contract.field_deltas == {"title": "review the launch checklist"}
    assert contract.preview_text == "Create inbox item: review the launch checklist"
    assert contract.confidence == 0.95
    assert contract.requires_confirmation is True
    assert contract.verification_status == "pass"
    assert turn.proposal_status == "pending"
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "capture_specialist",
        "verifier",
    ]
    assert engine.list_inbox() == []


def test_general_assistant_prompt_uses_agent_runtime_trace(engine: Engine) -> None:
    """General prompts should pilot the new runtime without creating writes."""
    turn = engine.send_assistant_prompt("What can you help with?")

    assert turn.route == "general"
    assert turn.proposal is None
    assert turn.proposal_status == "none"
    assert turn.response == (
        "I can help capture work, summarize today's plan, or save a preference. "
        "Right now you have 0 inbox items and 0 saved memories."
    )
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "deterministic",
        "verifier",
    ]


def test_agent_runtime_failure_falls_back_to_existing_general_response(
    db,
) -> None:
    """Runtime failures should degrade to the existing deterministic fallback."""
    from flow.agents import AgentRequest, AgentResult
    from flow.agents.runtime import AgentRuntime
    from flow.core.services import (
        AssistantService,
        DailyPlanService,
        MemoryService,
        ReviewService,
    )

    class FailingAdapter:
        name = "failing"

        def run(self, request: AgentRequest) -> AgentResult:
            raise RuntimeError("provider failed")

    service = AssistantService(
        db,
        DailyPlanService(db),
        ReviewService(db),
        MemoryService(db),
        agent_runtime=AgentRuntime(FailingAdapter()),
    )

    turn = service.send_prompt("What can you help with?")

    assert turn.route == "general"
    assert turn.response.startswith("I can help capture work")
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "runtime",
        "general_specialist",
        "verifier",
    ]


def test_assistant_contract_rejects_low_confidence_without_confirmation() -> None:
    """Unsafe agent contracts should fail validation before persistence."""
    with pytest.raises(ValidationError):
        AssistantProposal(
            action_type="create_task",
            title="Unsafe write",
            detail="Create inbox item without confirmation",
            requires_confirmation=False,
            payload={
                "title": "unsafe write",
                "agent_contract": {
                    "request_id": "req-1",
                    "action_type": "create_task",
                    "target_entity_ids": [],
                    "target_entity_versions": {},
                    "input_summary": "Add unsafe write",
                    "proposed_changes": ["Create inbox item"],
                    "field_deltas": {"title": "unsafe write"},
                    "preview_text": "Create inbox item: unsafe write",
                    "rationale": "User asked for a capture.",
                    "confidence": 0.5,
                    "requires_confirmation": False,
                    "verification_status": "pass",
                },
            },
        )


def test_assistant_turn_persistence_rejects_missing_agent_contract(
    db,
) -> None:
    """New action proposals should not persist without the shared agent contract."""
    turn = AssistantTurn(
        id="turn-without-contract",
        prompt="Add missing contract",
        response="I can add this.",
        route="capture",
        proposal=AssistantProposal(
            action_type="create_task",
            title="Add to Inbox",
            detail="Create inbox item: missing contract",
            payload={"title": "missing contract"},
            requires_confirmation=True,
        ),
        proposal_status="pending",
    )

    with pytest.raises(ValueError, match="agent_contract"):
        db.create_assistant_turn(turn)


def test_confirming_capture_turn_creates_inbox_item(engine: Engine) -> None:
    """Confirming a capture proposal should write the item into Inbox."""
    turn = engine.send_assistant_prompt("Add follow up with design team")

    confirmation = engine.confirm_assistant_proposal(turn.id)
    inbox_titles = [item.title for item in engine.list_inbox()]
    stored_turn = engine.list_assistant_turns(limit=5)[0]

    assert "Inbox" in confirmation
    assert "follow up with design team" in inbox_titles
    assert stored_turn.proposal_status == "confirmed"


def test_memory_prompt_only_persists_after_confirmation(engine: Engine) -> None:
    """Preference-like prompts should create inspectable memory only after confirmation."""
    turn = engine.send_assistant_prompt("Remember that I prefer deep work before lunch.")

    assert turn.route == "memory"
    assert turn.proposal is not None
    assert turn.proposal.action_type == "save_memory"
    contract = AssistantAgentContract.model_validate(
        turn.proposal.payload["agent_contract"]
    )
    assert contract.action_type == "save_memory"
    assert contract.requires_confirmation is True
    assert engine.list_memory_entries() == []

    engine.confirm_assistant_proposal(turn.id)

    entries = engine.list_memory_entries()
    assert len(entries) == 1
    assert entries[0].kind == "explicit_preference"
    assert "deep work before lunch" in entries[0].value


def test_memory_entries_can_be_updated_disabled_and_deleted(engine: Engine) -> None:
    """Memory management should support the inspect/edit/delete loop required by the UI."""
    entry = engine.create_memory_entry(
        kind="explicit_preference",
        scope="global",
        value="Protect mornings for strategy work.",
        source="manual",
        confidence=1.0,
    )

    updated = engine.update_memory_entry(entry.id, value="Protect afternoons for meetings.")
    disabled = engine.set_memory_entry_enabled(entry.id, enabled=False)

    assert updated.value == "Protect afternoons for meetings."
    assert disabled.enabled is False

    engine.delete_memory_entry(entry.id)

    assert engine.list_memory_entries() == []


def test_daily_plan_prompt_uses_structured_runtime_output(engine: Engine) -> None:
    """Daily-plan prompts should use structured planner output when runtime returns it."""
    top = Item(id="top-1", type="action", title="Top task", status="active")
    bonus = Item(id="bonus-1", type="action", title="Bonus task", status="active")
    engine._db.insert_inbox(top)  # type: ignore[attr-defined]
    engine._db.insert_inbox(bonus)  # type: ignore[attr-defined]
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-1"], bonus_item_ids=["bonus-1"])
    engine.create_memory_entry(
        kind="explicit_preference",
        scope="global",
        value="Protect mornings for deep work.",
        source="manual",
        confidence=1.0,
    )
    captured: dict[str, object] = {}

    class PlannerAdapter:
        name = "planner-test"

        def run(self, request: AgentRequest) -> AgentResult:
            captured["request"] = request
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "daily_planner",
                    "summary": "Protect the committed plan first.",
                    "focus_items": [
                        {
                            "item_id": "top-1",
                            "title": "Top task",
                            "energy": "high",
                            "reason": "It is already committed.",
                        },
                        {
                            "item_id": "bonus-1",
                            "title": "Bonus task",
                            "energy": "medium",
                            "reason": "Use it only if the first task lands.",
                        },
                    ],
                    "risks": ["Afternoon calendar gets tight."],
                    "follow_ups": ["Trim bonus work if inbox grows."],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="daily_planner",
                        summary="Generated planner output.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(PlannerAdapter())  # type: ignore[attr-defined]
    engine._assistant_service._calendar_availability_service = lambda: CalendarAvailability(  # type: ignore[attr-defined]
        available=True,
        next_free_window_minutes=90,
        minutes_until_next_event=120,
    )

    turn = engine.send_assistant_prompt("Plan my day", plan_date="2026-03-08")

    assert turn.route == "daily_plan"
    assert "Protect the committed plan first." in turn.response
    assert "Focus first on Top task, Bonus task." in turn.response
    assert "Watch for: Afternoon calendar gets tight.." in turn.response
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "daily_planner",
        "planning_specialist",
        "verifier",
    ]
    request = captured["request"]
    assert isinstance(request, AgentRequest)
    assert request.route_hint == "daily_plan"
    assert request.output_mode == "json"
    assert request.context["calendar"]["available"] is True
    assert request.context["workspace"]["top_items"][0]["title"] == "Top task"
    assert request.context["memory_summary"][0]["value"] == "Protect mornings for deep work."


def test_daily_plan_runtime_falls_back_when_structured_output_is_invalid(
    engine: Engine,
) -> None:
    """Invalid planner payloads should degrade to the existing daily-plan summary."""
    top = Item(id="top-1", type="action", title="Top task", status="active")
    engine._db.insert_inbox(top)  # type: ignore[attr-defined]
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-1"], bonus_item_ids=[])

    class InvalidPlannerAdapter:
        name = "planner-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "daily_planner",
                    "summary": "Broken payload",
                },
                provider=self.name,
            )

    engine._assistant_service._agent_runtime = AgentRuntime(InvalidPlannerAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Plan my day", plan_date="2026-03-08")

    assert turn.route == "daily_plan"
    assert turn.response == "Your plan for 2026-03-08 includes: Top task"
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "planning_specialist",
        "verifier",
    ]


def test_review_prompt_uses_structured_runtime_output(engine: Engine) -> None:
    """Weekly-review prompts should use structured reviewer output when available."""
    someday = Item(id="someday-1", type="action", title="Someday task", status="someday")
    engine._db.insert_inbox(someday)  # type: ignore[attr-defined]

    class ReviewAdapter:
        name = "review-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "weekly_reviewer",
                    "summary": "Weekly review is overdue on stale cleanup.",
                    "rationale": ["Several loose ends are still active."],
                    "cleanup_candidates": [
                        {
                            "item_id": "someday-1",
                            "title": "Someday task",
                            "issue": "someday_review",
                            "recommended_action": "Reconfirm or archive it.",
                        }
                    ],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="weekly_reviewer",
                        summary="Generated review output.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(ReviewAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Review my system")

    assert turn.route == "review"
    assert "Weekly review is overdue on stale cleanup." in turn.response
    assert "Start with Someday task." in turn.response
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "weekly_reviewer",
        "review_specialist",
        "verifier",
    ]


def test_review_prompt_persists_single_runtime_cleanup_proposal(engine: Engine) -> None:
    """Weekly-review runtime output may attach one bounded cleanup proposal."""
    stale = engine.capture("Old inbox task")

    class ReviewProposalAdapter:
        name = "review-proposal-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "weekly_reviewer",
                    "summary": "One stale item is safe to archive.",
                    "rationale": ["It has been untouched for weeks."],
                    "cleanup_candidates": [
                        {
                            "item_id": stale.id,
                            "title": "Old inbox task",
                            "issue": "stale",
                            "recommended_action": "Archive it.",
                        }
                    ],
                    "write_proposals": [
                        {
                            "action_type": "clean_up_inbox",
                            "title": "Archive stale item",
                            "detail": "Archive stale inbox item: Old inbox task",
                            "input_summary": "Review my system",
                            "proposed_changes": ["Archive stale inbox item"],
                            "field_deltas": {"status": "archived"},
                            "preview_text": "Archive stale item: Old inbox task",
                            "rationale": "The item is stale and no longer actionable.",
                            "confidence": 0.97,
                            "requires_confirmation": True,
                            "verification_status": "pass",
                            "payload": {
                                "operation": "archive_item",
                                "item_id": stale.id,
                            },
                            "target_entity_ids": [stale.id],
                            "target_entity_versions": {},
                        }
                    ],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="weekly_reviewer",
                        summary="Generated review output with one cleanup proposal.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(ReviewProposalAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Review my system")

    assert turn.route == "review"
    assert turn.proposal is not None
    assert turn.proposal_status == "pending"
    assert turn.proposal.action_type == "clean_up_inbox"
    assert turn.proposal.payload["operation"] == "archive_item"
    contract = AssistantAgentContract.model_validate(
        turn.proposal.payload["agent_contract"]
    )
    assert contract.request_id == turn.id
    assert contract.action_type == "clean_up_inbox"
    assert contract.target_entity_ids == [stale.id]
    assert contract.field_deltas == {"status": "archived"}
    assert "One stale item is safe to archive." in turn.response


def test_review_runtime_falls_back_when_structured_output_is_invalid(
    engine: Engine,
) -> None:
    """Invalid weekly-review payloads should degrade to the existing review summary."""
    someday = Item(id="someday-1", type="action", title="Someday task", status="someday")
    engine._db.insert_inbox(someday)  # type: ignore[attr-defined]

    class InvalidReviewAdapter:
        name = "review-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "weekly_reviewer",
                    "summary": "Broken payload",
                },
                provider=self.name,
            )

    engine._assistant_service._agent_runtime = AgentRuntime(InvalidReviewAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Weekly review")

    assert turn.route == "review"
    assert (
        turn.response
        == "Weekly review pressure is moderate: 0 stale items and 1 Someday items are currently available."
    )
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "review_specialist",
        "verifier",
    ]


def test_project_health_prompt_uses_structured_runtime_output(engine: Engine) -> None:
    """Project-health prompts should use structured runtime output when available."""
    project = engine.create_project("Launch prep", [])

    class ProjectHealthAdapter:
        name = "project-health-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "project_health",
                    "summary": "One project is drifting because it lacks a clear next action.",
                    "projects": [
                        {
                            "project_id": project.id,
                            "project_title": "Launch prep",
                            "status": "stalled",
                            "next_step": "Define one concrete next action.",
                            "blockers": ["No active next action"],
                        }
                    ],
                    "recommendations": ["Define one concrete next action for Launch prep."],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="project_health",
                        summary="Generated project-health output.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(ProjectHealthAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("What is the project status?")

    assert turn.route == "project_health"
    assert "One project is drifting because it lacks a clear next action." in turn.response
    assert "Launch prep (stalled)" in turn.response
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "project_health",
        "project_health_specialist",
        "verifier",
    ]


def test_project_health_prompt_persists_single_runtime_planning_proposal(
    engine: Engine,
) -> None:
    """Project-health runtime output may attach one bounded planning proposal."""
    action = engine.capture("Draft launch checklist")
    project = engine.create_project("Launch prep", [action.id])
    engine.defer_item(action.id, mode="waiting")
    captured: dict[str, object] = {}

    class ProjectHealthProposalAdapter:
        name = "project-health-proposal-test"

        def run(self, request: AgentRequest) -> AgentResult:
            captured["request"] = request
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "project_health",
                    "summary": "One project needs a clearer next action.",
                    "projects": [
                        {
                            "project_id": project.id,
                            "project_title": "Launch prep",
                            "status": "stalled",
                            "next_step": "Promote the waiting launch checklist action.",
                            "blockers": ["No active next action"],
                        }
                    ],
                    "recommendations": [
                        "Promote the waiting launch checklist action"
                    ],
                    "write_proposals": [
                        {
                            "action_type": "edit_task",
                            "title": "Promote project action",
                            "detail": "Promote the waiting launch checklist action.",
                            "input_summary": "What is the project status?",
                            "proposed_changes": [
                                "Promote one waiting project action to active"
                            ],
                            "field_deltas": {"status": "active"},
                            "preview_text": "Promote waiting project action: Draft launch checklist",
                            "rationale": "The project has a waiting action that can become the next step.",
                            "confidence": 0.96,
                            "requires_confirmation": True,
                            "verification_status": "pass",
                            "payload": {
                                "operation": "promote_project_action",
                                "item_id": action.id,
                            },
                            "target_entity_ids": [action.id],
                            "target_entity_versions": {},
                        }
                    ],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="project_health",
                        summary="Generated project-health output.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(ProjectHealthProposalAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("What is the project status?")

    assert turn.route == "project_health"
    assert turn.proposal_status == "pending"
    assert turn.proposal is not None
    assert turn.proposal.action_type == "edit_task"
    assert turn.proposal.payload["operation"] == "promote_project_action"
    assert turn.proposal.payload["item_id"] == action.id
    contract = AssistantAgentContract.model_validate(
        turn.proposal.payload["agent_contract"]
    )
    assert contract.request_id == turn.id
    assert contract.target_entity_ids == [action.id]
    assert contract.field_deltas == {"status": "active"}
    assert contract.verification_status == "pass"
    assert turn.response == (
        "One project needs a clearer next action. "
        "Current status: Launch prep (stalled). "
        "Next: Promote the waiting launch checklist action. "
        "A bounded project-health proposal is ready for confirmation."
    )
    assert captured["request"].capabilities == [
        "read_gtd_context",
        "propose_planning_change",
    ]
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "project_health",
        "project_health_specialist",
        "project_health_specialist",
        "verifier",
    ]
    assert any(
        step.summary == "Prepared one confirmation-gated project-health proposal."
        for step in turn.audit_steps
    )


def test_project_health_runtime_falls_back_when_structured_output_contains_disallowed_proposal(
    engine: Engine,
) -> None:
    """Disallowed project-health write proposals should fall back to deterministic text."""
    engine.create_project("Launch prep", [])

    class DisallowedProjectHealthAdapter:
        name = "project-health-disallowed-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "project_health",
                    "summary": "Broken payload",
                    "projects": [
                        {
                            "project_id": "project-1",
                            "project_title": "Launch prep",
                            "status": "stalled",
                            "next_step": "Save this as memory instead.",
                            "blockers": ["No active next action"],
                        }
                    ],
                    "write_proposals": [
                        {
                            "action_type": "save_memory",
                            "title": "Unsafe project-health write",
                            "detail": "Save the project status as memory.",
                            "input_summary": "Project status",
                            "proposed_changes": ["Save project-health output"],
                            "field_deltas": {"value": "Launch prep is stalled"},
                            "preview_text": "Save project status as memory",
                            "rationale": "This should be rejected for project health.",
                            "confidence": 0.99,
                            "requires_confirmation": True,
                            "verification_status": "pass",
                        }
                    ],
                },
                provider=self.name,
            )

    engine._assistant_service._agent_runtime = AgentRuntime(DisallowedProjectHealthAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Project status")

    assert turn.route == "project_health"
    assert turn.proposal is None
    assert turn.proposal_status == "none"
    assert turn.response == "You have 1 active projects. 1 do not have a clear next action."
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "project_health_specialist",
        "verifier",
    ]


def test_project_health_runtime_ignores_multiple_write_proposals_but_keeps_guidance(
    engine: Engine,
) -> None:
    """Multiple project-health proposals should be ignored without widening the turn shape."""
    action = engine.capture("Draft launch checklist")
    project = engine.create_project("Launch prep", [action.id])
    engine.defer_item(action.id, mode="waiting")

    class MultiProposalProjectHealthAdapter:
        name = "project-health-multi-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "project_health",
                    "summary": "One project needs a clearer next action.",
                    "projects": [
                        {
                            "project_id": project.id,
                            "project_title": "Launch prep",
                            "status": "stalled",
                            "next_step": "Promote the waiting launch checklist action.",
                            "blockers": ["No active next action"],
                        }
                    ],
                    "recommendations": ["Promote the waiting launch checklist action"],
                    "write_proposals": [
                        {
                            "action_type": "edit_task",
                            "title": "Promote project action",
                            "detail": "Promote the waiting launch checklist action.",
                            "input_summary": "What is the project status?",
                            "proposed_changes": [
                                "Promote one waiting project action to active"
                            ],
                            "field_deltas": {"status": "active"},
                            "preview_text": "Promote waiting project action: Draft launch checklist",
                            "rationale": "The project has a waiting action that can become the next step.",
                            "confidence": 0.96,
                            "requires_confirmation": True,
                            "verification_status": "pass",
                            "payload": {
                                "operation": "promote_project_action",
                                "item_id": action.id,
                            },
                            "target_entity_ids": [action.id],
                            "target_entity_versions": {},
                        },
                        {
                            "action_type": "edit_task",
                            "title": "Clarify project action",
                            "detail": "Clarify the project action in a different way.",
                            "input_summary": "What is the project status?",
                            "proposed_changes": [
                                "Clarify one waiting project action"
                            ],
                            "field_deltas": {"title": "Draft launch checklist"},
                            "preview_text": "Clarify waiting project action: Draft launch checklist",
                            "rationale": "This is a second proposal and should be ignored.",
                            "confidence": 0.95,
                            "requires_confirmation": True,
                            "verification_status": "pass",
                            "target_entity_ids": [action.id],
                            "target_entity_versions": {},
                        },
                    ],
                },
                provider=self.name,
                trace_events=[
                    AgentTraceEvent(
                        stage="project_health",
                        summary="Generated project-health output with multiple proposals.",
                        provider=self.name,
                    )
                ],
            )

    engine._assistant_service._agent_runtime = AgentRuntime(MultiProposalProjectHealthAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("What is the project status?")

    assert turn.route == "project_health"
    assert turn.proposal is None
    assert turn.proposal_status == "none"
    assert turn.response == (
        "One project needs a clearer next action. "
        "Current status: Launch prep (stalled). "
        "Next: Promote the waiting launch checklist action. "
        "No project-health proposal was attached because only one proposal is "
        "supported right now."
    )
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "project_health",
        "project_health_specialist",
        "project_health_specialist",
        "verifier",
    ]
    assert any(
        step.summary
        == "Ignored multiple project-health proposals; only one proposal is supported."
        for step in turn.audit_steps
    )


def test_project_health_runtime_falls_back_when_structured_output_is_invalid(
    engine: Engine,
) -> None:
    """Invalid project-health payloads should degrade to the deterministic fallback."""
    engine.create_project("Launch prep", [])

    class InvalidProjectHealthAdapter:
        name = "project-health-test"

        def run(self, request: AgentRequest) -> AgentResult:
            return AgentResult(
                response_text="",
                structured_output={
                    "kind": "project_health",
                    "summary": "Broken payload",
                },
                provider=self.name,
            )

    engine._assistant_service._agent_runtime = AgentRuntime(InvalidProjectHealthAdapter())  # type: ignore[attr-defined]

    turn = engine.send_assistant_prompt("Project status")

    assert turn.route == "project_health"
    assert turn.response == "You have 1 active projects. 1 do not have a clear next action."
    assert [step.stage for step in turn.audit_steps] == [
        "orchestrator",
        "runtime",
        "project_health_specialist",
        "verifier",
    ]
