"""Assistant orchestration service."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone

from pydantic import ValidationError

from flow.agents import AgentRequest
from flow.agents import validate_specialist_result, verify_specialist_result
from flow.agents.runtime import AgentRuntime
from flow.core.focus import CalendarAvailability
from flow.database.sqlite import SqliteDB
from flow.models import AssistantAgentContract, AssistantAuditStep, AssistantProposal, AssistantTurn
from flow.models import Item, MemoryEntry

from .daily_plan import DailyPlanService
from .memory import MemoryService
from .review import ReviewService


class AssistantService:
    """Deterministic assistant routing with explicit audit steps."""

    def __init__(
        self,
        db: SqliteDB,
        daily_plan_service: DailyPlanService,
        review_service: ReviewService,
        memory_service: MemoryService,
        agent_runtime: AgentRuntime | None = None,
        calendar_availability_service: Callable[[], CalendarAvailability] | None = None,
    ) -> None:
        self._db = db
        self._daily_plan_service = daily_plan_service
        self._review_service = review_service
        self._memory_service = memory_service
        self._agent_runtime = agent_runtime
        self._calendar_availability_service = calendar_availability_service

    def send_prompt(self, prompt: str, *, plan_date: str | None = None) -> AssistantTurn:
        """Analyze a prompt, persist the turn, and return the stored result."""
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt must not be empty")

        plan_day = plan_date or date.today().isoformat()
        context = self._build_context_snapshot(plan_day)
        route = self._detect_route(normalized_prompt)
        turn_id = str(uuid.uuid4())
        audit_steps = [
            AssistantAuditStep(
                stage="orchestrator",
                summary=f"Routed request to {route}.",
                payload=context,
            )
        ]

        proposal: AssistantProposal | None = None
        if route == "capture":
            capture_title = self._extract_capture_title(normalized_prompt)
            contract = self._build_agent_contract(
                request_id=turn_id,
                action_type="create_task",
                input_summary=normalized_prompt,
                proposed_changes=["Create inbox item"],
                field_deltas={"title": capture_title},
                preview_text=f"Create inbox item: {capture_title}",
                rationale="User asked Flow to capture a task-like item.",
                confidence=0.95,
                requires_confirmation=True,
                verification_status="pass",
            )
            proposal = AssistantProposal(
                action_type="create_task",
                title="Add to Inbox",
                detail=f"Create inbox item: {capture_title}",
                payload={
                    "title": capture_title,
                    "agent_contract": contract.model_dump(),
                },
                requires_confirmation=True,
            )
            response = f"I can add this to Inbox: {capture_title}"
            audit_steps.append(
                AssistantAuditStep(
                    stage="capture_specialist",
                    summary="Prepared a confirmation-gated inbox capture.",
                    payload={"title": capture_title},
                )
            )
        elif route == "memory":
            memory_value = self._extract_memory_value(normalized_prompt)
            contract = self._build_agent_contract(
                request_id=turn_id,
                action_type="save_memory",
                input_summary=normalized_prompt,
                proposed_changes=["Save explicit preference memory"],
                field_deltas={"value": memory_value},
                preview_text=f"Remember preference: {memory_value}",
                rationale="User made an explicit preference statement.",
                confidence=1.0,
                requires_confirmation=True,
                verification_status="pass",
            )
            proposal = AssistantProposal(
                action_type="save_memory",
                title="Save Memory",
                detail=f"Remember preference: {memory_value}",
                payload={
                    "kind": "explicit_preference",
                    "scope": "global",
                    "value": memory_value,
                    "source": "assistant-chat",
                    "confidence": 1.0,
                    "agent_contract": contract.model_dump(),
                },
                requires_confirmation=True,
            )
            response = f"I can save this as a preference memory: {memory_value}"
            audit_steps.append(
                AssistantAuditStep(
                    stage="memory_specialist",
                    summary="Prepared an explicit preference memory.",
                    payload={"value": memory_value},
                )
            )
        elif route == "daily_plan":
            response = self._build_daily_plan_response_with_runtime(
                normalized_prompt, plan_day, audit_steps
            )
        elif route == "review":
            response, proposal = self._build_review_response_with_runtime(
                normalized_prompt, audit_steps, request_id=turn_id
            )
        elif route == "project_health":
            response, proposal = self._build_project_health_response_with_runtime(
                normalized_prompt, audit_steps, request_id=turn_id
            )
        else:
            response = self._build_general_response_with_runtime(
                normalized_prompt, context, audit_steps
            )

        proposal_status = "pending" if proposal and proposal.requires_confirmation else "none"
        audit_steps.append(
            AssistantAuditStep(
                stage="verifier",
                summary="Checked that the proposal is bounded and requires confirmation before writes.",
                payload={"proposal_status": proposal_status},
            )
        )

        now = datetime.now(timezone.utc)
        turn = AssistantTurn(
            id=turn_id,
            prompt=normalized_prompt,
            response=response,
            route=route,
            proposal=proposal,
            proposal_status=proposal_status,
            audit_steps=audit_steps,
            created_at=now,
            updated_at=now,
        )
        self._db.create_assistant_turn(turn)
        self._db.create_assistant_audit_steps(turn.id, audit_steps)
        stored = self._db.get_assistant_turn(turn.id)
        if stored is None:
            raise RuntimeError("Assistant turn was not persisted")
        return stored

    def _build_agent_contract(
        self,
        *,
        request_id: str,
        action_type: str,
        input_summary: str,
        proposed_changes: list[str],
        field_deltas: dict[str, object],
        preview_text: str,
        rationale: str,
        confidence: float,
        requires_confirmation: bool,
        verification_status: str,
    ) -> AssistantAgentContract:
        """Build and validate the shared assistant proposal contract."""
        return AssistantAgentContract(
            request_id=request_id,
            action_type=action_type,  # type: ignore[arg-type]
            target_entity_ids=[],
            target_entity_versions={},
            input_summary=input_summary,
            proposed_changes=proposed_changes,
            field_deltas=field_deltas,
            preview_text=preview_text,
            rationale=rationale,
            confidence=confidence,
            requires_confirmation=requires_confirmation,
            verification_status=verification_status,  # type: ignore[arg-type]
        )

    def get_turn(self, turn_id: str) -> AssistantTurn | None:
        return self._db.get_assistant_turn(turn_id)

    def list_turns(self, limit: int = 30) -> list[AssistantTurn]:
        return self._db.list_assistant_turns(limit=limit)

    def set_proposal_status(self, turn_id: str, *, status: str) -> None:
        self._db.update_assistant_proposal_status(turn_id, status)

    def _build_context_snapshot(self, plan_date: str) -> dict[str, object]:
        active_actions = [
            item
            for item in self._db.list_actions(status="active")
            if item.type == "action"
        ]
        top_items, bonus_items = self._daily_plan_service.get_plan_items(plan_date)
        return {
            "inbox_count": len(self._db.list_inbox()),
            "active_action_count": len(active_actions),
            "plan_count": len(top_items) + len(bonus_items),
            "memory_count": len(self._memory_service.list_entries()),
        }

    def _build_general_response_with_runtime(
        self,
        prompt: str,
        context: dict[str, object],
        audit_steps: list[AssistantAuditStep],
    ) -> str:
        """Build a general response through the agent runtime when configured."""
        if self._agent_runtime is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="general_specialist",
                    summary="Answered using the current GTD system summary.",
                    payload=context,
                )
            )
            return self._build_fallback_response(context)

        result = self._agent_runtime.run(
            AgentRequest(
                prompt=prompt,
                route_hint="general",
                context=context,
                metadata={"surface": "assistant"},
            )
        )
        audit_steps.extend(
            AssistantAuditStep(
                stage=event.stage,
                summary=event.summary,
                payload=event.payload,
            )
            for event in result.trace_events
        )
        if not result.failed:
            return result.response_text

        audit_steps.append(
            AssistantAuditStep(
                stage="general_specialist",
                summary="Answered using the current GTD system summary.",
                payload=context,
            )
        )
        return self._build_fallback_response(context)

    def _build_daily_plan_response_with_runtime(
        self,
        prompt: str,
        plan_date: str,
        audit_steps: list[AssistantAuditStep],
    ) -> str:
        """Build a structured daily-planning response through the runtime when possible."""
        context = self._build_daily_plan_context(plan_date)
        if self._agent_runtime is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="planning_specialist",
                    summary="Summarized the current daily planning state.",
                    payload={"plan_date": plan_date},
                )
            )
            return self._build_daily_plan_response(plan_date)

        result = self._agent_runtime.run(
            AgentRequest(
                prompt=prompt,
                route_hint="daily_plan",
                context=context,
                output_mode="json",
                metadata={
                    "surface": "assistant",
                    "agent_name": "Flow Daily Planner",
                    "workflow_name": "Flow assistant daily plan",
                    "instructions": (
                        "You are Flow's daily planning specialist. Use the provided "
                        "context to summarize today's plan, pick the most important "
                        "focus items, call out concrete risks, and suggest bounded "
                        "follow-ups. Return only the structured daily planner JSON."
                    ),
                },
            )
        )
        audit_steps.extend(
            AssistantAuditStep(
                stage=event.stage,
                summary=event.summary,
                payload=event.payload,
            )
            for event in result.trace_events
        )
        if result.failed or result.structured_output is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="planning_specialist",
                    summary="Fell back to deterministic daily planning summary.",
                    payload={"plan_date": plan_date},
                )
            )
            return self._build_daily_plan_response(plan_date)

        try:
            specialist_result = validate_specialist_result(
                "daily_planner", result.structured_output
            )
            verify_specialist_result(
                specialist_result,
                capabilities=["read_gtd_context"],
            )
        except (ValidationError, ValueError):
            audit_steps.append(
                AssistantAuditStep(
                    stage="planning_specialist",
                    summary="Rejected invalid structured planner output and used fallback.",
                    payload={"plan_date": plan_date},
                )
            )
            return self._build_daily_plan_response(plan_date)

        audit_steps.append(
            AssistantAuditStep(
                stage="planning_specialist",
                summary="Generated structured daily planning guidance.",
                payload={
                    "plan_date": plan_date,
                    "focus_count": len(specialist_result.focus_items),
                    "risk_count": len(specialist_result.risks),
                },
            )
        )
        return self._render_daily_planner_response(specialist_result)

    def _detect_route(self, prompt: str) -> str:
        lowered = prompt.lower()
        if lowered.startswith("remember") or " i prefer " in f" {lowered} ":
            return "memory"
        if (
            lowered.startswith("add ")
            or lowered.startswith("capture ")
            or lowered.startswith("todo ")
            or lowered.startswith("remind me to ")
        ):
            return "capture"
        if "plan my day" in lowered or "today" in lowered:
            return "daily_plan"
        if "review" in lowered or "weekly" in lowered:
            return "review"
        if "project" in lowered and (
            "status" in lowered
            or "health" in lowered
            or "next step" in lowered
            or "what should i do next" in lowered
        ):
            return "project_health"
        return "general"

    def _extract_capture_title(self, prompt: str) -> str:
        cleaned = re.sub(r"^(add|capture|todo)\s+", "", prompt.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"^remind me to\s+", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip().rstrip(".") or prompt.strip()

    def _extract_memory_value(self, prompt: str) -> str:
        cleaned = re.sub(r"^remember(?: that)?\s+", "", prompt.strip(), flags=re.IGNORECASE)
        return cleaned.strip()

    def _build_daily_plan_response(self, plan_date: str) -> str:
        top_items, bonus_items = self._daily_plan_service.get_plan_items(plan_date)
        if top_items or bonus_items:
            titles = [item.title for item in top_items + bonus_items]
            return f"Your plan for {plan_date} includes: " + "; ".join(titles)
        inbox_count = len(self._db.list_inbox())
        return (
            f"You do not have a confirmed plan for {plan_date} yet. "
            f"There are {inbox_count} inbox items ready to review."
        )

    def _build_review_response_with_runtime(
        self,
        prompt: str,
        audit_steps: list[AssistantAuditStep],
        *,
        request_id: str,
    ) -> tuple[str, AssistantProposal | None]:
        context = self._build_review_context()
        if self._agent_runtime is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="review_specialist",
                    summary="Summarized stale work and review pressure.",
                    payload={"stale_count": len(self._review_service.get_stale())},
                )
            )
            return self._build_review_response(), None

        result = self._agent_runtime.run(
            AgentRequest(
                prompt=prompt,
                route_hint="review",
                context=context,
                capabilities=["read_gtd_context", "propose_review_cleanup"],
                output_mode="json",
                metadata={
                    "surface": "assistant",
                    "agent_name": "Flow Weekly Reviewer",
                    "workflow_name": "Flow assistant weekly review",
                    "instructions": (
                        "You are Flow's weekly review specialist. Summarize review "
                        "pressure, highlight the most important cleanup candidates, "
                        "and return only the structured weekly reviewer JSON."
                    ),
                },
            )
        )
        audit_steps.extend(
            AssistantAuditStep(
                stage=event.stage,
                summary=event.summary,
                payload=event.payload,
            )
            for event in result.trace_events
        )
        if result.failed or result.structured_output is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="review_specialist",
                    summary="Fell back to deterministic weekly review summary.",
                    payload={"stale_count": len(self._review_service.get_stale())},
                )
            )
            return self._build_review_response(), None

        try:
            specialist_result = validate_specialist_result(
                "weekly_reviewer", result.structured_output
            )
            verify_specialist_result(
                specialist_result,
                capabilities=["read_gtd_context", "propose_review_cleanup"],
            )
        except (ValidationError, ValueError):
            audit_steps.append(
                AssistantAuditStep(
                    stage="review_specialist",
                    summary="Rejected invalid structured review output and used fallback.",
                    payload={"stale_count": len(self._review_service.get_stale())},
                )
            )
            return self._build_review_response(), None

        audit_steps.append(
            AssistantAuditStep(
                stage="review_specialist",
                summary="Generated structured weekly review guidance.",
                payload={
                    "stale_count": len(context["stale_items"]),
                    "candidate_count": len(specialist_result.cleanup_candidates),
                },
            )
        )
        proposal: AssistantProposal | None = None
        proposal_count = len(specialist_result.write_proposals)
        if len(specialist_result.write_proposals) == 1:
            proposal = specialist_result.write_proposals[0].to_assistant_proposal(
                request_id=request_id
            )
            audit_steps.append(
                AssistantAuditStep(
                    stage="review_specialist",
                    summary="Prepared one confirmation-gated weekly review proposal.",
                    payload={"action_type": proposal.action_type},
                )
            )
        elif len(specialist_result.write_proposals) > 1:
            audit_steps.append(
                AssistantAuditStep(
                    stage="review_specialist",
                    summary="Ignored multiple weekly review proposals; only one proposal is supported.",
                    payload={"proposal_count": len(specialist_result.write_proposals)},
                )
            )
        return self._render_weekly_reviewer_response(specialist_result), proposal

    def _build_review_response(self) -> str:
        stale_count = len(self._review_service.get_stale())
        someday_count = len(self._review_service.get_someday_suggestions())
        return (
            f"Weekly review pressure is moderate: {stale_count} stale items and "
            f"{someday_count} Someday items are currently available."
        )

    def _build_project_health_response_with_runtime(
        self,
        prompt: str,
        audit_steps: list[AssistantAuditStep],
        *,
        request_id: str,
    ) -> tuple[str, AssistantProposal | None]:
        context = self._build_project_health_context()
        if self._agent_runtime is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="project_health_specialist",
                    summary="Summarized project status using deterministic context.",
                    payload={"project_count": len(context["projects"])},
                )
            )
            return self._build_project_health_fallback_response(context), None

        result = self._agent_runtime.run(
            AgentRequest(
                prompt=prompt,
                route_hint="project_health",
                context=context,
                capabilities=["read_gtd_context", "propose_planning_change"],
                output_mode="json",
                metadata={
                    "surface": "assistant",
                    "agent_name": "Flow Project Health Analyst",
                    "workflow_name": "Flow assistant project health",
                    "instructions": (
                        "You are Flow's project health specialist. Summarize project "
                        "status, point out blocked or stalled work, suggest the next "
                        "step, and return only the structured project health JSON."
                    ),
                },
            )
        )
        audit_steps.extend(
            AssistantAuditStep(
                stage=event.stage,
                summary=event.summary,
                payload=event.payload,
            )
            for event in result.trace_events
        )
        if result.failed or result.structured_output is None:
            audit_steps.append(
                AssistantAuditStep(
                    stage="project_health_specialist",
                    summary="Fell back to deterministic project-health summary.",
                    payload={"project_count": len(context["projects"])},
                )
            )
            return self._build_project_health_fallback_response(context), None

        try:
            specialist_result = validate_specialist_result(
                "project_health", result.structured_output
            )
            verify_specialist_result(
                specialist_result,
                capabilities=["read_gtd_context", "propose_planning_change"],
            )
        except (ValidationError, ValueError):
            audit_steps.append(
                AssistantAuditStep(
                    stage="project_health_specialist",
                    summary="Rejected invalid structured project-health output and used fallback.",
                    payload={"project_count": len(context["projects"])},
                )
            )
            return self._build_project_health_fallback_response(context), None

        audit_steps.append(
            AssistantAuditStep(
                stage="project_health_specialist",
                summary="Generated structured project-health guidance.",
                payload={
                    "project_count": len(specialist_result.projects),
                    "recommendation_count": len(specialist_result.recommendations),
                },
            )
        )
        proposal: AssistantProposal | None = None
        proposal_count = len(specialist_result.write_proposals)
        if proposal_count == 1:
            proposal = specialist_result.write_proposals[0].to_assistant_proposal(
                request_id=request_id
            )
            audit_steps.append(
                AssistantAuditStep(
                    stage="project_health_specialist",
                    summary="Prepared one confirmation-gated project-health proposal.",
                    payload={"action_type": proposal.action_type},
                )
            )
        elif proposal_count > 1:
            audit_steps.append(
                AssistantAuditStep(
                    stage="project_health_specialist",
                    summary="Ignored multiple project-health proposals; only one proposal is supported.",
                    payload={"proposal_count": proposal_count},
                )
            )

        response = self._render_project_health_response(specialist_result)
        if proposal is not None:
            response = (
                f"{response} A bounded project-health proposal is ready for confirmation."
            )
        elif proposal_count > 1:
            response = (
                f"{response} No project-health proposal was attached because only one proposal is supported right now."
            )
        return response, proposal

    def _build_review_context(self) -> dict[str, object]:
        stale_items = self._review_service.get_stale()
        someday_items = self._review_service.get_someday_suggestions()
        inbox_items = self._db.list_inbox()
        project_summaries = []
        for project in self._db.list_projects(status="active"):
            open_actions = [
                item
                for status in ("active", "waiting", "someday")
                for item in self._db.list_actions(status=status, parent_id=project.id)
                if item.type == "action"
            ]
            project_summaries.append(
                {
                    "project_id": project.id,
                    "project_title": project.title,
                    "open_action_count": len(open_actions),
                    "has_next_action": any(item.status == "active" for item in open_actions),
                }
            )
        return {
            "stale_items": [self._serialize_item(item) for item in stale_items[:10]],
            "someday_items": [self._serialize_item(item) for item in someday_items[:10]],
            "inbox_items": [self._serialize_item(item) for item in inbox_items[:10]],
            "project_summaries": project_summaries[:10],
        }

    def _build_project_health_context(self) -> dict[str, object]:
        projects = []
        for project in self._db.list_projects(status="active"):
            open_actions = [
                item
                for status in ("active", "waiting", "someday")
                for item in self._db.list_actions(status=status, parent_id=project.id)
                if item.type == "action"
            ]
            next_actions = [item for item in open_actions if item.status == "active"]
            projects.append(
                {
                    "project": self._serialize_item(project),
                    "open_actions": [self._serialize_item(item) for item in open_actions[:10]],
                    "next_action": (
                        self._serialize_item(next_actions[0]) if next_actions else None
                    ),
                    "waiting_count": sum(item.status == "waiting" for item in open_actions),
                    "someday_count": sum(item.status == "someday" for item in open_actions),
                }
            )
        return {"projects": projects}

    def _build_daily_plan_context(self, plan_date: str) -> dict[str, object]:
        workspace = self._build_daily_workspace_snapshot(plan_date)
        memories = self._memory_service.list_entries(include_disabled=False)[:5]
        calendar = self._get_calendar_availability()
        return {
            "plan_date": plan_date,
            "workspace": workspace,
            "calendar": {
                "available": calendar.available,
                "next_free_window_minutes": calendar.next_free_window_minutes,
                "minutes_until_next_event": calendar.minutes_until_next_event,
            },
            "memory_summary": [self._serialize_memory_entry(entry) for entry in memories],
        }

    def _build_daily_workspace_snapshot(self, plan_date: str) -> dict[str, object]:
        top_items, bonus_items = self._daily_plan_service.get_plan_items(plan_date)
        planned_ids = {item.id for item in top_items + bonus_items}
        return {
            "needs_plan": not self._daily_plan_service.has_saved_plan(plan_date),
            "top_items": [self._serialize_item(item) for item in top_items],
            "bonus_items": [self._serialize_item(item) for item in bonus_items],
            "candidates": {
                key: [self._serialize_item(item) for item in items]
                for key, items in self._build_daily_workspace_candidates(
                    date.fromisoformat(plan_date),
                    planned_ids=planned_ids,
                ).items()
            },
            "unplanned_work": {
                key: [self._serialize_item(item) for item in items]
                for key, items in self._build_daily_unplanned_work(planned_ids).items()
            },
        }

    def _build_daily_workspace_candidates(
        self, plan_day: date, planned_ids: set[str]
    ) -> dict[str, list[Item]]:
        inbox_items = [item for item in self._db.list_inbox() if item.id not in planned_ids]
        active_actions = [
            item
            for item in self._db.list_actions(status="active")
            if item.type == "action"
            and item.id not in planned_ids
            and self._is_deferred_until_active(item)
        ]
        must_address = [
            item
            for item in active_actions
            if self._daily_plan_service.is_due_on_or_before(item, plan_day)
        ]
        must_address_ids = {item.id for item in must_address}
        ready_actions = [
            item
            for item in active_actions
            if item.parent_id is None and item.id not in must_address_ids
        ]
        project_tasks = [
            item
            for item in active_actions
            if item.parent_id is not None and item.id not in must_address_ids
        ]
        return {
            "must_address": must_address,
            "inbox": inbox_items,
            "ready_actions": ready_actions,
            "project_tasks": project_tasks,
            "suggested": [],
        }

    def _build_daily_unplanned_work(self, planned_ids: set[str]) -> dict[str, list[Item]]:
        active_actions = [
            item
            for item in self._db.list_actions(status="active")
            if item.type == "action"
            and item.id not in planned_ids
            and self._is_deferred_until_active(item)
        ]
        return {
            "inbox": [item for item in self._db.list_inbox() if item.id not in planned_ids],
            "next_actions": [item for item in active_actions if item.parent_id is None],
            "project_tasks": [item for item in active_actions if item.parent_id is not None],
        }

    def _is_deferred_until_active(self, item: Item) -> bool:
        raw_defer_until = item.meta_payload.get("defer_until")
        if not raw_defer_until:
            return True
        try:
            defer_until = datetime.fromisoformat(str(raw_defer_until))
        except ValueError:
            return True
        now = datetime.now(defer_until.tzinfo or timezone.utc)
        if defer_until.tzinfo is None:
            now = now.replace(tzinfo=None)
        return defer_until <= now

    def _get_calendar_availability(self) -> CalendarAvailability:
        if self._calendar_availability_service is None:
            return CalendarAvailability(
                available=False,
                next_free_window_minutes=None,
                minutes_until_next_event=None,
            )
        try:
            return self._calendar_availability_service()
        except Exception:
            return CalendarAvailability(
                available=False,
                next_free_window_minutes=None,
                minutes_until_next_event=None,
            )

    def _serialize_item(self, item: Item) -> dict[str, object]:
        return {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "status": item.status,
            "parent_id": item.parent_id,
            "estimated_duration": item.estimated_duration,
            "due_date": item.due_date.isoformat() if item.due_date else None,
        }

    def _serialize_memory_entry(self, entry: MemoryEntry) -> dict[str, object]:
        return {
            "id": entry.id,
            "kind": entry.kind,
            "scope": entry.scope,
            "value": entry.value,
            "confidence": entry.confidence,
        }

    def _render_daily_planner_response(self, specialist_result: object) -> str:
        focus_items = getattr(specialist_result, "focus_items", [])
        risks = getattr(specialist_result, "risks", [])
        follow_ups = getattr(specialist_result, "follow_ups", [])
        summary = str(getattr(specialist_result, "summary", "")).strip()
        focus_text = ", ".join(item.title for item in focus_items[:3])
        parts = [summary] if summary else []
        if focus_text:
            parts.append(f"Focus first on {focus_text}.")
        if risks:
            parts.append(f"Watch for: {'; '.join(risks[:2])}.")
        if follow_ups:
            parts.append(f"Next: {'; '.join(follow_ups[:2])}.")
        return " ".join(parts).strip() or self._build_fallback_response(
            self._build_context_snapshot(date.today().isoformat())
        )

    def _render_weekly_reviewer_response(self, specialist_result: object) -> str:
        summary = str(getattr(specialist_result, "summary", "")).strip()
        candidates = getattr(specialist_result, "cleanup_candidates", [])
        rationale = getattr(specialist_result, "rationale", [])
        parts = [summary] if summary else []
        if candidates:
            candidate_titles = ", ".join(candidate.title for candidate in candidates[:3])
            parts.append(f"Start with {candidate_titles}.")
        if rationale:
            parts.append(f"Why: {'; '.join(rationale[:2])}.")
        return " ".join(parts).strip() or self._build_review_response()

    def _render_project_health_response(self, specialist_result: object) -> str:
        summary = str(getattr(specialist_result, "summary", "")).strip()
        projects = getattr(specialist_result, "projects", [])
        recommendations = getattr(specialist_result, "recommendations", [])
        parts = [summary] if summary else []
        if projects:
            project_summaries = ", ".join(
                f"{project.project_title} ({project.status})" for project in projects[:3]
            )
            parts.append(f"Current status: {project_summaries}.")
        if recommendations:
            parts.append(f"Next: {'; '.join(recommendations[:2])}.")
        return " ".join(parts).strip() or self._build_project_health_fallback_response(
            self._build_project_health_context()
        )

    def _build_project_health_fallback_response(self, context: dict[str, object]) -> str:
        projects = context["projects"]
        if not projects:
            return "You do not have any active projects to review right now."
        without_next_action = sum(1 for project in projects if project["next_action"] is None)
        return (
            f"You have {len(projects)} active projects. "
            f"{without_next_action} do not have a clear next action."
        )

    def _build_fallback_response(self, context: dict[str, object]) -> str:
        return (
            "I can help capture work, summarize today's plan, or save a preference. "
            f"Right now you have {context['inbox_count']} inbox items and "
            f"{context['memory_count']} saved memories."
        )
