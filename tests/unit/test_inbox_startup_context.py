"""Unit tests for Inbox startup context handoff and behavior."""

from __future__ import annotations

import asyncio
from typing import Any

from flow.models import Item
from flow.tui.app import FlowApp
from flow.tui.screens.inbox.inbox import InboxScreen


class _FakeOptionList:
    def __init__(self) -> None:
        self.highlighted: int | None = None
        self.options: list[object] = []
        self.focus_calls = 0

    def clear_options(self) -> None:
        self.options.clear()

    def add_option(self, option: object) -> None:
        self.options.append(option)

    def action_first(self) -> None:
        self.highlighted = 0 if self.options else None

    def focus(self) -> None:
        self.focus_calls += 1


class _FakeContainer:
    def __init__(self) -> None:
        self.display = False


class _FakeStatic:
    def __init__(self) -> None:
        self.value: object = ""

    def update(self, value: object) -> None:
        self.value = value


def _item(item_id: str, title: str) -> Item:
    return Item(id=item_id, type="inbox", title=title, status="active")


def test_flow_app_passes_startup_context_to_default_inbox(monkeypatch: Any) -> None:
    """FlowApp should pass startup context through when opening Inbox by default."""
    pushes: list[object] = []
    contexts: list[dict[str, object] | None] = []
    startup_context = {"highlighted_item_id": "item-1", "show_first_value_hint": True}

    class _FakeInboxScreen:
        def __init__(self, startup_context: dict[str, object] | None = None) -> None:
            contexts.append(startup_context)

    monkeypatch.setattr("flow.tui.app.InboxScreen", _FakeInboxScreen)
    monkeypatch.setattr(FlowApp, "_start_index_worker", staticmethod(lambda: None))
    monkeypatch.setattr(FlowApp, "push_screen", lambda self, screen: pushes.append(screen))

    app = FlowApp(startup_context=startup_context)
    app.on_mount()

    assert len(pushes) == 1
    assert contexts == [startup_context]


def test_inbox_refresh_uses_startup_highlight_and_shows_hint_once(
    monkeypatch: Any,
) -> None:
    """Inbox should highlight startup item and show first-value hint once."""
    screen = InboxScreen(
        startup_context={
            "highlighted_item_id": "item-2",
            "show_first_value_hint": True,
        }
    )
    screen._items = [_item("item-1", "First"), _item("item-2", "Second")]
    notices: list[str] = []
    option_list = _FakeOptionList()

    widgets = {
        "#inbox-list": option_list,
        "#inbox-empty": _FakeContainer(),
        "#inbox-empty-content": _FakeStatic(),
        "#inbox-content": _FakeContainer(),
        "#inbox-count": _FakeStatic(),
        "#inbox-stats-content": _FakeStatic(),
        "#inbox-detail-body": _FakeStatic(),
        "#inbox-detail-tags": _FakeStatic(),
    }

    def _query_one(selector: str, *_args: object, **_kwargs: object) -> object:
        return widgets[selector]

    monkeypatch.setattr(screen, "query_one", _query_one)
    monkeypatch.setattr(screen, "notify", lambda message, **_kwargs: notices.append(message))

    screen._refresh_list()
    first_highlight = option_list.highlighted
    screen._refresh_list()

    assert first_highlight == 1
    assert notices == ["Captured your first inbox item. Start by clarifying the next action."]


def test_inbox_startup_context_triggers_new_task_flow_once(
    monkeypatch: Any,
) -> None:
    """Inbox startup context should open startup quick-create once then clear."""
    screen = InboxScreen(startup_context={"start_new_task": True})
    opened: list[bool] = []

    monkeypatch.setattr(screen, "_open_startup_quick_capture", lambda: opened.append(True))

    screen._consume_startup_context_once()
    screen._consume_startup_context_once()

    assert opened == [True]
    assert screen._startup_context is None


def test_inbox_startup_quick_capture_submit_creates_item_and_refreshes(
    monkeypatch: Any,
) -> None:
    """Submitting startup quick capture should capture text and refresh inbox."""
    screen = InboxScreen()
    captured_texts: list[str] = []
    refreshed: list[bool] = []
    highlighted_ids: list[str] = []
    notices: list[str] = []

    class _FakeEngine:
        def capture(self, text: str) -> Item:
            captured_texts.append(text)
            return _item("new-item", text)

    async def _fake_to_thread(func: Any, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    async def _fake_refresh() -> None:
        refreshed.append(True)

    screen._engine = _FakeEngine()
    monkeypatch.setattr("flow.tui.screens.inbox.inbox.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr(screen, "_refresh_items_async", _fake_refresh)
    monkeypatch.setattr(screen, "_highlight_item_by_id", lambda item_id: highlighted_ids.append(item_id))
    monkeypatch.setattr(screen, "notify", lambda message, **_kwargs: notices.append(message))

    asyncio.run(
        screen._apply_startup_quick_capture_result_async(
            {"action": "submit", "text": "  Plan Q2 roadmap  "}
        )
    )

    assert captured_texts == ["Plan Q2 roadmap"]
    assert refreshed == [True]
    assert highlighted_ids == ["new-item"]
    assert any("Captured" in message for message in notices)


def test_inbox_startup_quick_capture_blank_submit_warns_and_skips_capture(
    monkeypatch: Any,
) -> None:
    """Blank startup quick capture should not create an item."""
    screen = InboxScreen()
    notices: list[tuple[str, str]] = []

    class _FakeEngine:
        def capture(self, text: str) -> Item:
            raise AssertionError(f"capture should not be called for blank text: {text}")

    screen._engine = _FakeEngine()
    monkeypatch.setattr(
        screen,
        "notify",
        lambda message, **kwargs: notices.append((message, str(kwargs.get("severity", "")))),
    )

    asyncio.run(
        screen._apply_startup_quick_capture_result_async(
            {"action": "submit", "text": "   "}
        )
    )

    assert notices
    assert any("Enter task text" in message for message, _ in notices)
