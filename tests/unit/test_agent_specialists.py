from __future__ import annotations

import pytest

from pydantic import ValidationError

from flow.agents import AgentWriteProposal, validate_specialist_result, verify_specialist_result


def _build_write_proposal(action_type: str) -> AgentWriteProposal:
    return AgentWriteProposal(
        action_type=action_type,  # type: ignore[arg-type]
        title="Proposal title",
        detail="Proposal detail",
        input_summary="Summarize current state",
        proposed_changes=["Change one thing"],
        field_deltas={"title": "Updated"},
        preview_text="Preview",
        rationale="Reason",
        confidence=0.95,
        requires_confirmation=True,
        verification_status="pass",
    )


def test_validate_daily_planner_result_accepts_structured_payload() -> None:
    result = validate_specialist_result(
        "daily_planner",
        {
            "kind": "daily_planner",
            "summary": "Focus on two priorities.",
            "rationale": ["Inbox is under control."],
            "focus_items": [
                {
                    "item_id": "task-1",
                    "title": "Ship roadmap update",
                    "energy": "high",
                    "reason": "Deep work block is available.",
                }
            ],
            "risks": ["Calendar is tight after 3pm."],
            "follow_ups": ["Defer low-value errands."],
        },
    )

    assert result.kind == "daily_planner"
    assert result.focus_items[0].title == "Ship roadmap update"


def test_validate_inbox_clarifier_result_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        validate_specialist_result(
            "inbox_clarifier",
            {
                "kind": "inbox_clarifier",
                "summary": "Need more detail.",
                "clarifications": [{"source_item_id": "item-1"}],
            },
        )


def test_verify_specialist_result_requires_matching_capability() -> None:
    result = validate_specialist_result(
        "memory_curator",
        {
            "kind": "memory_curator",
            "summary": "Found one stable preference.",
            "memory_candidates": [
                {
                    "value": "Prefer deep work before lunch.",
                    "kind": "explicit_preference",
                    "scope": "global",
                    "action": "save",
                    "reason": "Repeated preference statement.",
                }
            ],
            "write_proposals": [_build_write_proposal("save_memory").model_dump()],
        },
    )

    with pytest.raises(ValueError, match="propose_memory_write"):
        verify_specialist_result(result, capabilities=["read_gtd_context"])


def test_verify_specialist_result_rejects_disallowed_action_type() -> None:
    result = validate_specialist_result(
        "daily_planner",
        {
            "kind": "daily_planner",
            "summary": "Suggest a trimmed plan.",
            "focus_items": [
                {
                    "title": "Review backlog",
                    "energy": "medium",
                    "reason": "Fits available time.",
                }
            ],
            "write_proposals": [_build_write_proposal("save_memory").model_dump()],
        },
    )

    with pytest.raises(ValueError, match="does not allow action_type save_memory"):
        verify_specialist_result(
            result,
            capabilities=["read_gtd_context", "propose_planning_change"],
        )


def test_agent_write_proposal_converts_to_assistant_proposal() -> None:
    proposal = _build_write_proposal("save_memory")

    assistant_proposal = proposal.to_assistant_proposal(request_id="req-123")

    assert assistant_proposal.action_type == "save_memory"
    assert assistant_proposal.requires_confirmation is True
    assert assistant_proposal.payload["agent_contract"]["request_id"] == "req-123"
    assert assistant_proposal.payload["agent_contract"]["action_type"] == "save_memory"


def test_validate_project_health_result_accepts_read_only_payload() -> None:
    result = validate_specialist_result(
        "project_health",
        {
            "kind": "project_health",
            "summary": "Two projects need attention.",
            "projects": [
                {
                    "project_id": "project-1",
                    "project_title": "Launch prep",
                    "status": "at_risk",
                    "next_step": "Assign next owner",
                    "blockers": ["No clear next action"],
                }
            ],
            "recommendations": ["Clarify the next action for Launch prep."],
        },
    )

    verify_specialist_result(result, capabilities=["read_gtd_context"])

    assert result.kind == "project_health"
    assert result.projects[0].status == "at_risk"


def test_verify_project_health_result_accepts_single_edit_task_proposal() -> None:
    result = validate_specialist_result(
        "project_health",
        {
            "kind": "project_health",
            "summary": "One project needs a clearer next action.",
            "projects": [
                {
                    "project_id": "project-1",
                    "project_title": "Launch prep",
                    "status": "stalled",
                    "next_step": "Promote the waiting action.",
                    "blockers": ["No active next action"],
                }
            ],
            "recommendations": ["Promote the waiting launch checklist action."],
            "write_proposals": [
                _build_write_proposal("edit_task")
                .model_copy(
                    update={
                        "title": "Promote project action",
                        "detail": "Promote the waiting launch checklist action.",
                        "input_summary": "What is the project status?",
                        "proposed_changes": ["Promote one waiting project action to active"],
                        "field_deltas": {"status": "active"},
                        "preview_text": "Promote waiting project action: Launch checklist",
                        "rationale": "The project has a waiting action that can become the next step.",
                        "payload": {
                            "operation": "promote_project_action",
                            "item_id": "action-1",
                        },
                        "target_entity_ids": ["action-1"],
                    }
                )
                .model_dump()
            ],
        },
    )

    verify_specialist_result(
        result,
        capabilities=["read_gtd_context", "propose_planning_change"],
    )

    assistant_proposal = result.write_proposals[0].to_assistant_proposal(
        request_id="req-project-health-1"
    )

    assert assistant_proposal.action_type == "edit_task"
    assert assistant_proposal.payload["operation"] == "promote_project_action"
    assert assistant_proposal.payload["agent_contract"]["request_id"] == "req-project-health-1"
    assert assistant_proposal.payload["agent_contract"]["target_entity_ids"] == [
        "action-1"
    ]


def test_verify_weekly_reviewer_result_accepts_single_cleanup_proposal() -> None:
    result = validate_specialist_result(
        "weekly_reviewer",
        {
            "kind": "weekly_reviewer",
            "summary": "One stale item should be archived.",
            "cleanup_candidates": [
                {
                    "item_id": "item-1",
                    "title": "Archive me",
                    "issue": "stale",
                    "recommended_action": "Archive it.",
                }
            ],
            "write_proposals": [
                _build_write_proposal("clean_up_inbox").model_copy(
                    update={
                        "payload": {
                            "operation": "archive_item",
                            "item_id": "item-1",
                        },
                        "target_entity_ids": ["item-1"],
                        "field_deltas": {"status": "archived"},
                        "preview_text": "Archive stale item: Archive me",
                    }
                ).model_dump()
            ],
        },
    )

    verify_specialist_result(
        result,
        capabilities=["read_gtd_context", "propose_review_cleanup"],
    )

    assistant_proposal = result.write_proposals[0].to_assistant_proposal(
        request_id="req-review-1"
    )
    assert assistant_proposal.action_type == "clean_up_inbox"
    assert assistant_proposal.payload["operation"] == "archive_item"
    assert assistant_proposal.payload["agent_contract"]["action_type"] == "clean_up_inbox"
