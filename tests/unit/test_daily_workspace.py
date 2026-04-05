"""Unit tests for daily workspace planning and recap behavior."""

from datetime import datetime, timezone
from pathlib import Path

from flow.core.engine import Engine
from flow.core.focus import CalendarAvailability
from flow.models import Item


def test_get_daily_workspace_state_requires_plan_when_none_exists(temp_db_path: Path) -> None:
    """Workspace state should report planning mode when no plan exists."""
    engine = Engine(db_path=temp_db_path)
    engine.capture("Clarify launch checklist", skip_auto_tag=True)

    state = engine.get_daily_workspace_state("2026-03-08")

    assert state["needs_plan"] is True
    assert state["top_items"] == []
    assert state["bonus_items"] == []
    assert len(state["candidates"]["inbox"]) == 1


def test_save_daily_plan_exposes_top_and_bonus_items(temp_db_path: Path) -> None:
    """Saved daily plan should come back split into Top 3 and Bonus buckets."""
    engine = Engine(db_path=temp_db_path)
    top = Item(id="top-1", type="action", title="Top", status="active")
    bonus = Item(id="bonus-1", type="action", title="Bonus", status="active")
    engine._db.insert_inbox(top)  # type: ignore[attr-defined]
    engine._db.insert_inbox(bonus)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["top-1"],
        bonus_item_ids=["bonus-1"],
    )

    state = engine.get_daily_workspace_state("2026-03-08")

    assert state["needs_plan"] is False
    assert [item.id for item in state["top_items"]] == ["top-1"]
    assert [item.id for item in state["bonus_items"]] == ["bonus-1"]


def test_save_daily_plan_deduplicates_item_ids_before_persisting(
    temp_db_path: Path,
) -> None:
    """Saving a plan should normalize duplicate item ids instead of crashing persistence."""
    engine = Engine(db_path=temp_db_path)
    for item in (
        Item(id="task-1", type="action", title="Task 1", status="active"),
        Item(id="task-2", type="action", title="Task 2", status="active"),
    ):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["task-1", "task-1"],
        bonus_item_ids=["task-1", "task-2"],
    )

    state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in state["top_items"]] == ["task-1"]
    assert [item.id for item in state["bonus_items"]] == ["task-2"]


def test_daily_workspace_hides_non_active_planned_items(temp_db_path: Path) -> None:
    """Workspace should only show still-active planned tasks."""
    engine = Engine(db_path=temp_db_path)
    active_top = Item(id="top-active", type="action", title="Top", status="active")
    done_top = Item(id="top-done", type="action", title="Done", status="done")
    archived_bonus = Item(
        id="bonus-archived", type="action", title="Archived", status="archived"
    )
    for item in (active_top, done_top, archived_bonus):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["top-active", "top-done"],
        bonus_item_ids=["bonus-archived"],
    )

    state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in state["top_items"]] == ["top-active"]
    assert state["bonus_items"] == []


def test_get_daily_workspace_candidates_groups_must_address_ready_inbox_and_project_tasks(
    temp_db_path: Path,
) -> None:
    """Workspace should group candidates by planning role."""
    engine = Engine(db_path=temp_db_path)
    inbox_item = Item(id="inbox-1", type="inbox", title="Inbox", status="active")
    due_item = Item(
        id="due-1",
        type="action",
        title="Due today",
        status="active",
        due_date=datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc),
    )
    ready_item = Item(id="ready-1", type="action", title="Ready", status="active")
    suggested_item = Item(
        id="project-1",
        type="project",
        title="Ship redesign",
        status="active",
    )
    suggested_next = Item(
        id="project-task-1",
        type="action",
        title="Draft rollout notes",
        status="active",
        parent_id="project-1",
    )
    second_project_task = Item(
        id="project-task-2",
        type="action",
        title="Review checklist",
        status="active",
        parent_id="project-1",
    )
    for item in (
        inbox_item,
        due_item,
        ready_item,
        suggested_item,
        suggested_next,
        second_project_task,
    ):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in state["candidates"]["must_address"]] == ["due-1"]
    assert [item.id for item in state["candidates"]["inbox"]] == ["inbox-1"]
    assert [item.id for item in state["candidates"]["ready_actions"]] == ["ready-1"]
    assert [item.id for item in state["candidates"]["project_tasks"]] == [
        "project-task-1",
        "project-task-2",
    ]
    assert state["candidates"]["suggested"] == []


def test_confirmed_workspace_exposes_grouped_unplanned_work_and_readds_removed_items(
    temp_db_path: Path,
) -> None:
    """Confirmed workspace should keep unplanned work grouped by original source."""
    engine = Engine(db_path=temp_db_path)
    inbox_item = Item(id="inbox-1", type="inbox", title="Inbox", status="active")
    next_action = Item(
        id="next-1",
        type="action",
        title="Next",
        status="active",
    )
    project = Item(
        id="project-1",
        type="project",
        title="Project",
        status="active",
    )
    planned_project_task = Item(
        id="project-task-1",
        type="action",
        title="Planned project task",
        status="active",
        parent_id="project-1",
    )
    remaining_project_task = Item(
        id="project-task-2",
        type="action",
        title="Remaining project task",
        status="active",
        parent_id="project-1",
    )
    for item in (
        inbox_item,
        next_action,
        project,
        planned_project_task,
        remaining_project_task,
    ):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["inbox-1"],
        bonus_item_ids=["project-task-1"],
    )

    state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in state["unplanned_work"]["inbox"]] == []
    assert [item.id for item in state["unplanned_work"]["next_actions"]] == ["next-1"]
    assert [item.id for item in state["unplanned_work"]["project_tasks"]] == [
        "project-task-2"
    ]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["inbox-1"],
        bonus_item_ids=[],
    )

    updated_state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in updated_state["unplanned_work"]["project_tasks"]] == [
        "project-task-1",
        "project-task-2",
    ]


def test_engine_finds_latest_prior_unrecapped_plan_date(temp_db_path: Path) -> None:
    """Engine should expose the most recent prior plan that still needs recap."""
    engine = Engine(db_path=temp_db_path)
    item = Item(id="task-1", type="action", title="Task", status="active")
    engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan("2026-03-07", top_item_ids=["task-1"], bonus_item_ids=[])
    engine.save_daily_plan("2026-03-08", top_item_ids=["task-1"], bonus_item_ids=[])
    engine.mark_daily_plan_recapped("2026-03-07")

    assert engine.get_latest_unrecapped_plan_date("2026-03-08") is None
    assert engine.get_latest_unrecapped_plan_date("2026-03-09") == "2026-03-08"


def test_completed_saved_plan_still_blocks_recap_gate_until_recapped(
    temp_db_path: Path,
) -> None:
    """A completed saved plan should remain a recap target instead of reverting to planning."""
    engine = Engine(db_path=temp_db_path)
    completed = Item(id="top-done", type="action", title="Top done", status="done")
    engine._db.insert_inbox(completed)  # type: ignore[attr-defined]

    engine.save_daily_plan("2026-03-08", top_item_ids=["top-done"], bonus_item_ids=[])

    state = engine.get_daily_workspace_state("2026-03-08")

    assert state["needs_plan"] is False
    assert state["top_items"] == []
    assert state["bonus_items"] == []
    assert engine.get_daily_recap_summary("2026-03-08")["completed_top_items"] == [
        {"id": "top-done", "title": "Top done"}
    ]


def test_get_daily_recap_summary_returns_rich_structured_feedback(temp_db_path: Path) -> None:
    """Daily recap should include deterministic verdicts and planned-item lists."""
    engine = Engine(db_path=temp_db_path)
    top_done = Item(id="top-done", type="action", title="Top done", status="done")
    top_open = Item(id="top-open", type="action", title="Top open", status="active")
    bonus_done = Item(id="bonus-done", type="action", title="Bonus done", status="done")
    for item in (top_done, top_open, bonus_done):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["top-done", "top-open"],
        bonus_item_ids=["bonus-done"],
    )

    recap = engine.get_daily_recap_summary("2026-03-08")

    assert recap["top_total"] == 2
    assert recap["top_completed"] == 1
    assert recap["bonus_total"] == 1
    assert recap["bonus_completed"] == 1
    assert recap["all_top_completed"] is False
    assert recap["completed_top_items"] == [{"id": "top-done", "title": "Top done"}]
    assert recap["completed_bonus_items"] == [{"id": "bonus-done", "title": "Bonus done"}]
    assert recap["open_planned_items"] == [{"id": "top-open", "title": "Top open"}]
    assert recap["headline"]
    assert recap["coaching_feedback"]


def test_get_daily_recap_summary_marks_all_top_complete_as_strong_day(
    temp_db_path: Path,
) -> None:
    """Completing the full Top 3 should produce a positive verdict."""
    engine = Engine(db_path=temp_db_path)
    for index in range(1, 4):
        engine._db.insert_inbox(  # type: ignore[attr-defined]
            Item(
                id=f"top-{index}",
                type="action",
                title=f"Top {index}",
                status="done",
            )
        )

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["top-1", "top-2", "top-3"],
        bonus_item_ids=[],
    )

    recap = engine.get_daily_recap_summary("2026-03-08")

    assert recap["headline"] == "Strong day"
    assert "Top 3" in recap["coaching_feedback"]
    assert recap["open_planned_items"] == []


def test_get_daily_recap_summary_flags_overloaded_plan(
    temp_db_path: Path,
) -> None:
    """Incomplete Top 3 plus many bonuses should trigger improvement coaching."""
    engine = Engine(db_path=temp_db_path)
    items = [
        Item(id="top-1", type="action", title="Top 1", status="done"),
        Item(id="top-2", type="action", title="Top 2", status="active"),
        Item(id="top-3", type="action", title="Top 3", status="active"),
        Item(id="bonus-1", type="action", title="Bonus 1", status="done"),
        Item(id="bonus-2", type="action", title="Bonus 2", status="active"),
        Item(id="bonus-3", type="action", title="Bonus 3", status="active"),
    ]
    for item in items:
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    engine.save_daily_plan(
        "2026-03-08",
        top_item_ids=["top-1", "top-2", "top-3"],
        bonus_item_ids=["bonus-1", "bonus-2", "bonus-3"],
    )

    recap = engine.get_daily_recap_summary("2026-03-08")

    assert recap["headline"] == "Plan was too ambitious"
    assert "bonus" in recap["coaching_feedback"].lower()
    assert recap["open_planned_items"] == [
        {"id": "top-2", "title": "Top 2"},
        {"id": "top-3", "title": "Top 3"},
        {"id": "bonus-2", "title": "Bonus 2"},
        {"id": "bonus-3", "title": "Bonus 3"},
    ]


def test_generate_daily_recap_insight_returns_llm_summary_when_available(
    monkeypatch, temp_db_path: Path
) -> None:
    """Daily recap insight should return the provider output when available."""
    engine = Engine(db_path=temp_db_path)
    engine._db.insert_inbox(  # type: ignore[attr-defined]
        Item(id="top-done", type="action", title="Top done", status="done")
    )
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-done"], bonus_item_ids=[])

    monkeypatch.setattr(
        "flow.core.services.daily_plan.complete",
        lambda prompt, **_kwargs: "You finished the important work first.",
    )

    insight = engine.generate_daily_recap_insight("2026-03-08")

    assert insight == "You finished the important work first."


def test_generate_daily_recap_insight_returns_none_without_provider(
    monkeypatch, temp_db_path: Path
) -> None:
    """Daily recap insight should fall back cleanly when no provider responds."""
    engine = Engine(db_path=temp_db_path)
    engine._db.insert_inbox(  # type: ignore[attr-defined]
        Item(id="top-open", type="action", title="Top open", status="active")
    )
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-open"], bonus_item_ids=[])

    monkeypatch.setattr(
        "flow.core.services.daily_plan.complete",
        lambda prompt, **_kwargs: None,
    )

    assert engine.generate_daily_recap_insight("2026-03-08") is None


def test_engine_get_calendar_availability_exposes_compact_summary(
    monkeypatch, temp_db_path: Path
) -> None:
    """Engine should return only the calendar summary Daily Workspace needs."""
    engine = Engine(db_path=temp_db_path)
    expected = CalendarAvailability(
        available=True,
        next_free_window_minutes=45,
        minutes_until_next_event=60,
    )

    monkeypatch.setattr(engine, "_calendar_availability_service", lambda: expected)

    assert engine.get_calendar_availability() == expected


def test_engine_get_calendar_availability_degrades_to_unavailable_on_failure(
    monkeypatch, temp_db_path: Path
) -> None:
    """Calendar provider failures should not escape through the engine."""
    engine = Engine(db_path=temp_db_path)

    def _raise() -> CalendarAvailability:
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(engine, "_calendar_availability_service", _raise)

    assert engine.get_calendar_availability() == CalendarAvailability(
        available=False,
        next_free_window_minutes=None,
        minutes_until_next_event=None,
    )
