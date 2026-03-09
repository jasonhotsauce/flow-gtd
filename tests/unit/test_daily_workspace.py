"""Unit tests for daily workspace planning and wrap behavior."""

from datetime import datetime, timezone
from pathlib import Path

from flow.core.engine import Engine
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


def test_get_daily_workspace_candidates_groups_must_address_ready_and_inbox(
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
    for item in (inbox_item, due_item, ready_item, suggested_item, suggested_next):
        engine._db.insert_inbox(item)  # type: ignore[attr-defined]

    state = engine.get_daily_workspace_state("2026-03-08")

    assert [item.id for item in state["candidates"]["must_address"]] == ["due-1"]
    assert [item.id for item in state["candidates"]["inbox"]] == ["inbox-1"]
    assert [item.id for item in state["candidates"]["ready_actions"]] == ["ready-1"]
    assert [item.id for item in state["candidates"]["suggested"]] == ["project-task-1"]


def test_get_daily_wrap_summary_uses_plan_completion_counts(temp_db_path: Path) -> None:
    """Daily wrap should summarize completed Top 3 and Bonus items."""
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

    wrap = engine.get_daily_wrap_summary("2026-03-08")

    assert wrap == {
        "top_total": 2,
        "top_completed": 1,
        "bonus_total": 1,
        "bonus_completed": 1,
        "all_top_completed": False,
    }


def test_generate_daily_wrap_insight_returns_llm_summary_when_available(
    monkeypatch, temp_db_path: Path
) -> None:
    """Daily wrap insight should return the provider output when available."""
    engine = Engine(db_path=temp_db_path)
    engine._db.insert_inbox(  # type: ignore[attr-defined]
        Item(id="top-done", type="action", title="Top done", status="done")
    )
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-done"], bonus_item_ids=[])

    monkeypatch.setattr(
        "flow.core.services.daily_plan.complete",
        lambda prompt, **_kwargs: "You finished the important work first.",
    )

    insight = engine.generate_daily_wrap_insight("2026-03-08")

    assert insight == "You finished the important work first."


def test_generate_daily_wrap_insight_returns_none_without_provider(
    monkeypatch, temp_db_path: Path
) -> None:
    """Daily wrap insight should fall back cleanly when no provider responds."""
    engine = Engine(db_path=temp_db_path)
    engine._db.insert_inbox(  # type: ignore[attr-defined]
        Item(id="top-open", type="action", title="Top open", status="active")
    )
    engine.save_daily_plan("2026-03-08", top_item_ids=["top-open"], bonus_item_ids=[])

    monkeypatch.setattr(
        "flow.core.services.daily_plan.complete",
        lambda prompt, **_kwargs: None,
    )

    assert engine.generate_daily_wrap_insight("2026-03-08") is None
