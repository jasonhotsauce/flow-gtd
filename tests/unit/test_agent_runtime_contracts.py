from __future__ import annotations

import pytest
from pydantic import ValidationError

from flow.agents import (
    AgentRequest,
    AgentResult,
    AgentTraceEvent,
    AgentWriteProposal,
)
from flow.models import AssistantAgentContract


def test_agent_request_defaults_to_safe_read_only_capabilities() -> None:
    request = AgentRequest(prompt="What should I focus on today?")

    assert request.capabilities == ["read_gtd_context"]
    assert request.context == {}
    assert request.metadata == {}


def test_agent_result_rejects_write_proposal_without_confirmation() -> None:
    proposal = AgentWriteProposal(
        action_type="create_task",
        title="Add task",
        detail="Create an inbox item",
        input_summary="Add follow up",
        proposed_changes=["Create inbox item"],
        field_deltas={"title": "Follow up"},
        preview_text="Create inbox item: Follow up",
        rationale="The user asked to capture a task.",
        confidence=0.99,
        requires_confirmation=False,
        verification_status="pass",
    )

    with pytest.raises(ValidationError, match="requires_confirmation"):
        AgentResult(response_text="Ready", write_proposals=[proposal])


def test_write_proposal_converts_to_assistant_agent_contract_payload() -> None:
    proposal = AgentWriteProposal(
        action_type="save_memory",
        title="Save preference",
        detail="Remember the preference",
        input_summary="Remember that mornings are best for deep work",
        proposed_changes=["Save explicit preference memory"],
        field_deltas={"value": "Mornings are best for deep work"},
        preview_text="Remember preference: Mornings are best for deep work",
        rationale="The user made an explicit preference statement.",
        confidence=1.0,
        requires_confirmation=True,
        verification_status="pass",
        target_entity_ids=["memory:new"],
        target_entity_versions={"memory:new": "pending"},
    )

    payload = proposal.to_agent_contract_payload(request_id="turn-1")
    contract = AssistantAgentContract.model_validate(payload)

    assert contract.request_id == "turn-1"
    assert contract.action_type == "save_memory"
    assert contract.target_entity_ids == ["memory:new"]
    assert contract.target_entity_versions == {"memory:new": "pending"}
    assert contract.requires_confirmation is True


def test_trace_event_serializes_without_sensitive_raw_prompt() -> None:
    event = AgentTraceEvent(
        stage="runtime",
        summary="Built safe context summary.",
        payload={
            "input_summary": "3 inbox items, 2 active projects",
            "raw_prompt": "do not serialize this",
            "nested": {
                "prompt": "also do not serialize this",
                "safe_count": 3,
            },
            "messages": [{"role": "user", "content": "private task"}],
        },
    )

    assert event.model_dump()["payload"] == {
        "input_summary": "3 inbox items, 2 active projects",
        "nested": {"safe_count": 3},
    }
