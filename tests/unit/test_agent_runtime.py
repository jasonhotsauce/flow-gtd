from __future__ import annotations

from flow.agents import AgentRequest, AgentResult, AgentWriteProposal
from flow.agents.runtime import AgentRuntime
from flow.agents.adapters.deterministic import DeterministicAgentAdapter


class FailingAdapter:
    name = "failing"

    def run(self, request: AgentRequest) -> AgentResult:
        raise RuntimeError("provider leaked raw user prompt")


class UnsafeWriteAdapter:
    name = "unsafe"

    def run(self, request: AgentRequest) -> AgentResult:
        proposal = AgentWriteProposal(
            action_type="create_task",
            title="Add task",
            detail="Create an inbox item",
            input_summary=request.prompt,
            proposed_changes=["Create inbox item"],
            field_deltas={"title": "Follow up"},
            preview_text="Create inbox item: Follow up",
            rationale="The user asked to capture a task.",
            confidence=0.99,
            requires_confirmation=False,
            verification_status="pass",
        )
        return AgentResult.model_construct(
            response_text="Unsafe",
            write_proposals=[proposal],
            provider=self.name,
        )


class ConfirmedWriteAdapter:
    name = "confirmed-write"

    def run(self, request: AgentRequest) -> AgentResult:
        proposal = AgentWriteProposal(
            action_type="create_task",
            title="Add task",
            detail="Create an inbox item",
            input_summary=request.prompt,
            proposed_changes=["Create inbox item"],
            field_deltas={"title": "Follow up"},
            preview_text="Create inbox item: Follow up",
            rationale="The user asked to capture a task.",
            confidence=0.99,
            requires_confirmation=True,
            verification_status="pass",
        )
        return AgentResult(
            response_text="Confirmed write",
            write_proposals=[proposal],
            provider=self.name,
        )


class ReviewCleanupAdapter:
    name = "review-cleanup"

    def run(self, request: AgentRequest) -> AgentResult:
        proposal = AgentWriteProposal(
            action_type="clean_up_inbox",
            title="Archive stale item",
            detail="Archive stale inbox item: Old task",
            input_summary=request.prompt,
            proposed_changes=["Archive stale inbox item"],
            field_deltas={"status": "archived"},
            preview_text="Archive stale item: Old task",
            rationale="The weekly review surfaced one stale item to archive.",
            confidence=0.97,
            requires_confirmation=True,
            verification_status="pass",
            payload={"operation": "archive_item", "item_id": "item-1"},
            target_entity_ids=["item-1"],
        )
        return AgentResult(
            response_text="Prepared a weekly review cleanup.",
            write_proposals=[proposal],
            provider=self.name,
        )


class ProjectHealthPlanningAdapter:
    name = "project-health-planning"

    def run(self, request: AgentRequest) -> AgentResult:
        proposal = AgentWriteProposal(
            action_type="edit_task",
            title="Promote project action",
            detail="Promote the waiting launch checklist action.",
            input_summary=request.prompt,
            proposed_changes=["Promote one waiting project action to active"],
            field_deltas={"status": "active"},
            preview_text="Promote waiting project action: Launch checklist",
            rationale="The project has a waiting action that should become active.",
            confidence=0.96,
            requires_confirmation=True,
            verification_status="pass",
            payload={
                "operation": "promote_project_action",
                "item_id": "action-1",
            },
            target_entity_ids=["action-1"],
        )
        return AgentResult(
            response_text="Prepared a project-health planning proposal.",
            write_proposals=[proposal],
            provider=self.name,
        )


def test_runtime_runs_deterministic_adapter_and_records_trace() -> None:
    runtime = AgentRuntime(
        DeterministicAgentAdapter(response_text="Runtime response")
    )

    result = runtime.run(AgentRequest(prompt="Summarize my system"))

    assert result.response_text == "Runtime response"
    assert result.provider == "deterministic"
    assert [event.stage for event in result.trace_events] == [
        "runtime",
        "deterministic",
    ]


def test_runtime_wraps_adapter_error_as_safe_result() -> None:
    runtime = AgentRuntime(FailingAdapter())

    result = runtime.run(AgentRequest(prompt="Sensitive task content"))

    assert result.failed is True
    assert result.response_text == ""
    assert result.provider == "failing"
    assert "Sensitive task content" not in str(result.model_dump())
    assert result.trace_events[-1].summary == "Agent runtime adapter failed safely."


def test_runtime_rejects_adapter_write_without_confirmed_contract() -> None:
    runtime = AgentRuntime(UnsafeWriteAdapter())

    result = runtime.run(AgentRequest(prompt="Add follow up"))

    assert result.failed is True
    assert result.write_proposals == []
    assert result.trace_events[-1].stage == "runtime_verifier"


def test_runtime_rejects_write_proposals_without_matching_capability() -> None:
    runtime = AgentRuntime(
        ConfirmedWriteAdapter(),
    )

    result = runtime.run(
        AgentRequest(
            prompt="Add follow up",
            capabilities=["read_gtd_context"],
        )
    )

    assert result.failed is True
    assert result.write_proposals == []
    assert result.trace_events[-1].summary == (
        "Rejected agent write proposal outside requested capabilities."
    )


def test_runtime_rejects_edit_task_without_planning_capability() -> None:
    runtime = AgentRuntime(ProjectHealthPlanningAdapter())

    result = runtime.run(
        AgentRequest(
            prompt="What is the project status?",
            capabilities=["read_gtd_context"],
        )
    )

    assert result.failed is True
    assert result.write_proposals == []
    assert result.trace_events[-1].summary == (
        "Rejected agent write proposal outside requested capabilities."
    )


def test_runtime_accepts_review_cleanup_with_matching_capability() -> None:
    runtime = AgentRuntime(ReviewCleanupAdapter())

    result = runtime.run(
        AgentRequest(
            prompt="Review my system",
            capabilities=["read_gtd_context", "propose_review_cleanup"],
        )
    )

    assert result.failed is False
    assert result.write_proposals[0].action_type == "clean_up_inbox"
    assert result.write_proposals[0].payload["operation"] == "archive_item"


def test_runtime_accepts_edit_task_with_planning_capability() -> None:
    runtime = AgentRuntime(ProjectHealthPlanningAdapter())

    result = runtime.run(
        AgentRequest(
            prompt="What is the project status?",
            capabilities=["read_gtd_context", "propose_planning_change"],
        )
    )

    assert result.failed is False
    assert result.write_proposals[0].action_type == "edit_task"
    assert result.write_proposals[0].target_entity_ids == ["action-1"]
    assert result.write_proposals[0].field_deltas == {"status": "active"}
