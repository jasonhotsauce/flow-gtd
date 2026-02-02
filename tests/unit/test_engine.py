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
    """next_actions returns active items."""
    engine.capture("Task one")
    engine.capture("Task two")
    actions = engine.next_actions()
    assert len(actions) >= 2


def test_weekly_report(engine: Engine) -> None:
    """weekly_report returns markdown string."""
    report = engine.weekly_report()
    assert "# Flow Weekly Report" in report
    assert "**Completed:**" in report
