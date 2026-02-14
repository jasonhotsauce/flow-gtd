"""Unit tests for Engine (capture, list_inbox, next_actions)."""

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
