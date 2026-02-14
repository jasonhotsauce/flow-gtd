"""Unit tests for Engine (capture, list_inbox, next_actions)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from flow.core.engine import Engine


@pytest.fixture
def engine(temp_db_path: Path) -> Engine:
    """Engine with temp DB."""
    return Engine(db_path=temp_db_path)


def test_capture(engine: Engine) -> None:
    """capture creates inbox item and returns it."""
    item = engine.capture("Hello world")
    assert item.title == "Hello world"
    assert item.type == "inbox"
    items = engine.list_inbox()
    assert len(items) == 1
    assert items[0].title == "Hello world"


def test_next_actions(engine: Engine) -> None:
    """next_actions returns active actionable items (not projects)."""
    grouped = engine.capture("Grouped task")
    engine.capture("Standalone task")
    engine.create_project("Website refresh", [grouped.id])

    actions = engine.next_actions()
    assert len(actions) >= 2
    assert all(item.type != "project" for item in actions)


def test_next_actions_with_project_titles(engine: Engine) -> None:
    """next_actions_with_project_titles includes project title for grouped tasks."""
    grouped = engine.capture("Write launch draft")
    standalone = engine.capture("Book dentist")
    project = engine.create_project("Product launch", [grouped.id])

    rows = engine.next_actions_with_project_titles()
    by_id = {item.id: project_title for item, project_title in rows}

    assert by_id[grouped.id] == project.title
    assert by_id[standalone.id] is None


def test_weekly_report(engine: Engine) -> None:
    """weekly_report returns markdown string (completed this week)."""
    report = engine.weekly_report()
    assert "# Flow Weekly Report" in report
    assert "**Completed this week:**" in report


def test_list_inbox_excludes_done_and_archived(engine: Engine) -> None:
    """list_inbox returns only open inbox items (excludes done and archived)."""
    engine.capture("Open task")
    engine.capture("To be completed")
    engine.capture("To be archived")

    items = engine.list_inbox()
    assert len(items) == 3

    ids = [it.id for it in items]
    engine.complete_item(ids[1])
    engine.archive_item(ids[2])

    items = engine.list_inbox()
    assert len(items) == 1
    assert items[0].title == "Open task"


def test_defer_waiting_sets_waiting_status(engine: Engine) -> None:
    """defer_item waiting mode sets status to waiting."""
    item = engine.capture("Call vendor")
    engine.defer_item(item.id, mode="waiting")
    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "waiting"


def test_defer_someday_sets_someday_status(engine: Engine) -> None:
    """defer_item someday mode sets status to someday."""
    item = engine.capture("Maybe learn SwiftUI")
    engine.defer_item(item.id, mode="someday")
    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "someday"


def test_list_inbox_excludes_deferred_and_project_items(engine: Engine) -> None:
    """list_inbox hides deferred items and items that belong to projects."""
    visible = engine.capture("Visible")
    waiting = engine.capture("Waiting")
    someday = engine.capture("Someday")
    grouped = engine.capture("Grouped")

    engine.defer_item(waiting.id, mode="waiting")
    engine.defer_item(someday.id, mode="someday")
    engine.create_project("Plan launch", [grouped.id])

    items = engine.list_inbox()
    assert len(items) == 1
    assert items[0].id == visible.id


def test_list_inbox_excludes_future_defer_until(engine: Engine) -> None:
    """list_inbox hides items deferred until a future datetime."""
    visible = engine.capture("Visible now")
    deferred = engine.capture("Deferred until later")
    future = datetime.now() + timedelta(days=1)
    engine.defer_item(deferred.id, mode="until", defer_until=future)

    items = engine.list_inbox()
    item_ids = {item.id for item in items}
    assert visible.id in item_ids
    assert deferred.id not in item_ids


def test_defer_until_stores_timestamp_and_hides_from_next_actions(
    engine: Engine,
) -> None:
    """defer_item until mode stores defer_until and excludes from next actions."""
    item = engine.capture("Write proposal")
    future = datetime.now() + timedelta(days=2)
    engine.defer_item(item.id, mode="until", defer_until=future)

    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "active"
    assert "defer_until" in updated.meta_payload

    visible_ids = {it.id for it in engine.next_actions()}
    assert item.id not in visible_ids


def test_defer_until_due_item_is_visible_in_next_actions(engine: Engine) -> None:
    """Active item deferred until the past stays visible in next actions."""
    item = engine.capture("Prepare meeting notes")
    past = datetime.now() - timedelta(hours=1)
    engine.defer_item(item.id, mode="until", defer_until=past)

    visible_ids = {it.id for it in engine.next_actions()}
    assert item.id in visible_ids


def test_defer_until_aware_future_datetime_is_hidden(engine: Engine) -> None:
    """Aware defer_until in the future should not crash and should hide item."""
    item = engine.capture("Submit expense report")
    future = datetime.now(timezone.utc) + timedelta(days=1)
    engine.defer_item(item.id, mode="until", defer_until=future)

    visible_ids = {it.id for it in engine.next_actions()}
    assert item.id not in visible_ids


def test_defer_until_aware_past_datetime_is_visible(engine: Engine) -> None:
    """Aware defer_until in the past should not crash and should show item."""
    item = engine.capture("Follow up with recruiter")
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    engine.defer_item(item.id, mode="until", defer_until=past)

    visible_ids = {it.id for it in engine.next_actions()}
    assert item.id in visible_ids
