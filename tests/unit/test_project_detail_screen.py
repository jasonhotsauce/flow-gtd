"""Unit tests for project detail task rendering guidance."""

from datetime import datetime

from flow.models import Item
from flow.tui.screens.projects.project_detail import ProjectDetailScreen


def test_empty_guidance_prompts_completion_or_more_tasks() -> None:
    """When no open tasks remain, suggest project completion or adding tasks."""
    project = Item(id="project-1", type="project", title="Launch", status="active")
    screen = ProjectDetailScreen(project)

    message = screen._empty_guidance_message()

    assert "Complete this project" in message
    assert "add more tasks" in message


def test_state_label_marks_waiting_someday_and_deferred_until() -> None:
    """List labels should expose deferred task state for user visibility."""
    project = Item(id="project-2", type="project", title="Roadmap", status="active")
    screen = ProjectDetailScreen(project)

    waiting = Item(id="w1", type="inbox", title="W", status="waiting")
    someday = Item(id="s1", type="inbox", title="S", status="someday")
    deferred_active = Item(
        id="d1",
        type="inbox",
        title="D",
        status="active",
        meta_payload={"defer_until": "2099-01-01T10:00:00+00:00"},
    )
    next_action = Item(id="a1", type="inbox", title="A", status="active")

    assert screen._state_label(waiting).lower() == "waiting for"
    assert screen._state_label(someday).lower() == "someday/maybe"
    deferred_label = screen._state_label(deferred_active).lower()
    assert "deferred until" in deferred_label
    assert "2099-01-01" in deferred_label
    assert screen._state_label(next_action).lower() == "next action"


def test_status_summary_surfaces_defer_until_timestamp() -> None:
    """Selected deferred task should expose concrete defer-until timestamp."""
    project = Item(id="project-3", type="project", title="Plan", status="active")
    screen = ProjectDetailScreen(project)

    deferred_active = Item(
        id="d2",
        type="inbox",
        title="Wait for launch date",
        status="active",
        meta_payload={"defer_until": "2026-03-01T15:30:00+00:00"},
    )

    summary = screen._status_summary(deferred_active, datetime(2026, 2, 14, 9, 0, 0))
    assert "Deferred until" in summary
    assert "2026-03-01 15:30" in summary
