"""Unit tests for Inbox process menu routing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from flow.models import Item
from flow.tui.common.widgets.process_task_dialog import ProcessTaskDialog
from flow.tui.screens.inbox.inbox import InboxScreen


def _sample_item() -> Item:
    return Item(id="item-1", type="inbox", title="Inbox task", status="active")


def test_open_process_menu_pushes_process_dialog(monkeypatch: Any) -> None:
    """Enter action should open the process-task dialog for selected item."""
    screen = InboxScreen()
    screen._items = [_sample_item()]
    pushes: list[tuple[object, object | None]] = []

    opt_list = SimpleNamespace(highlighted=0)
    monkeypatch.setattr(screen, "query_one", lambda *_args, **_kwargs: opt_list)
    monkeypatch.setattr(
        InboxScreen,
        "app",
        property(
            lambda _self: SimpleNamespace(
                push_screen=lambda dialog, callback=None: pushes.append(
                    (dialog, callback)
                )
            )
        ),
    )

    screen.action_open_process_menu()

    assert len(pushes) == 1
    assert isinstance(pushes[0][0], ProcessTaskDialog)


def test_apply_process_result_add_to_project_opens_picker(monkeypatch: Any) -> None:
    """Process result add_to_project should open project picker."""
    screen = InboxScreen()
    opened: list[str] = []
    monkeypatch.setattr(
        screen, "_open_project_picker", lambda item_id: opened.append(item_id)
    )

    screen._apply_process_result("item-1", {"action": "add_to_project"})

    assert opened == ["item-1"]


@pytest.mark.asyncio
async def test_open_project_picker_warns_when_no_active_projects(monkeypatch: Any) -> None:
    """Should warn and avoid opening picker when there are no projects."""
    screen = InboxScreen()
    notices: list[tuple[str, str]] = []
    pushes: list[object] = []
    monkeypatch.setattr(
        screen,
        "notify",
        lambda message, severity="information", timeout=0: notices.append(
            (message, severity)
        ),
    )
    monkeypatch.setattr(
        screen._engine,
        "get_item",
        lambda _item_id: Item(id="item-1", type="inbox", title="Task", status="active"),
    )
    monkeypatch.setattr(screen._engine, "list_projects", lambda: [])
    monkeypatch.setattr(
        InboxScreen,
        "app",
        property(
            lambda _self: SimpleNamespace(
                push_screen=lambda dialog, callback=None: pushes.append(dialog)
            )
        ),
    )

    await screen._open_project_picker_async("item-1")

    assert pushes == []
    assert any("No active projects yet" in message for message, _ in notices)


@pytest.mark.asyncio
async def test_open_project_picker_refreshes_when_item_missing(monkeypatch: Any) -> None:
    """Missing item should notify and trigger refresh."""
    screen = InboxScreen()
    notices: list[tuple[str, str]] = []
    refreshed: list[bool] = []
    monkeypatch.setattr(
        screen,
        "notify",
        lambda message, severity="information", timeout=0: notices.append(
            (message, severity)
        ),
    )
    monkeypatch.setattr(screen, "_refresh_list", lambda: refreshed.append(True))
    monkeypatch.setattr(screen._engine, "get_item", lambda _item_id: None)

    await screen._open_project_picker_async("missing-id")

    assert refreshed == [True]
    assert any("Item no longer exists" in message for message, _ in notices)


@pytest.mark.asyncio
async def test_apply_project_assignment_handles_engine_error(monkeypatch: Any) -> None:
    """Assignment errors should show toast and refresh list."""
    screen = InboxScreen()
    notices: list[tuple[str, str]] = []
    refreshed: list[bool] = []
    monkeypatch.setattr(
        screen,
        "notify",
        lambda message, severity="information", timeout=0: notices.append(
            (message, severity)
        ),
    )
    monkeypatch.setattr(screen, "_refresh_list", lambda: refreshed.append(True))

    def _raise(_item_id: str, _project_id: str) -> None:
        raise ValueError("Project is not assignable")

    monkeypatch.setattr(screen._engine, "assign_item_to_project", _raise)

    await screen._apply_project_assignment_async("item-1", {"project_id": "project-1"})

    assert refreshed == [True]
    assert ("Project is not assignable", "error") in notices
