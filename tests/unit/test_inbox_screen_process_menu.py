"""Unit tests for Inbox process menu routing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from flow.models import Item
from flow.tui.screens.inbox.inbox import InboxScreen


def _sample_item() -> Item:
    return Item(id="item-1", type="inbox", title="Inbox task", status="active")


def test_open_process_menu_pushes_process_dialog(monkeypatch: Any) -> None:
    """Enter action should open the process-task dialog for selected item."""
    screen = InboxScreen()
    screen._items = [_sample_item()]
    screen.app = SimpleNamespace(push_screen=lambda *_args, **_kwargs: None)

    opt_list = SimpleNamespace(highlighted=0)
    monkeypatch.setattr(screen, "query_one", lambda *_args, **_kwargs: opt_list)

    screen.action_open_process_menu()


def test_apply_process_result_add_to_project_opens_picker(monkeypatch: Any) -> None:
    """Process result add_to_project should open project picker."""
    screen = InboxScreen()
    opened: list[str] = []
    monkeypatch.setattr(screen, "_open_project_picker", lambda item_id: opened.append(item_id))

    screen._apply_process_result("item-1", {"action": "add_to_project"})

    assert opened == ["item-1"]
