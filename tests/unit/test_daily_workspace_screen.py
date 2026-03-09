"""Unit tests for the daily workspace screen."""

import asyncio

import pytest
from textual.app import App, ComposeResult

from flow.models import Item
from flow.tui.screens.daily_workspace.daily_workspace import DailyWorkspaceScreen


def _has_binding(screen: type[DailyWorkspaceScreen], key: str, action: str | None = None) -> bool:
    for binding in screen.BINDINGS:
        if isinstance(binding, tuple):
            if binding[0] != key:
                continue
            if action is None or binding[1] == action:
                return True
            continue
        if binding.key != key:
            continue
        if action is None or binding.action == action:
            return True
    return False


def test_daily_workspace_screen_exposes_plan_focus_and_wrap_bindings() -> None:
    """Workspace should expose the primary planning and execution actions."""
    assert _has_binding(DailyWorkspaceScreen, "t", "add_to_top")
    assert _has_binding(DailyWorkspaceScreen, "b", "add_to_bonus")
    assert _has_binding(DailyWorkspaceScreen, "x", "confirm_plan")
    assert _has_binding(DailyWorkspaceScreen, "c", "complete_planned_item")
    assert _has_binding(DailyWorkspaceScreen, "w", "show_daily_wrap")
    assert _has_binding(DailyWorkspaceScreen, "I", "generate_wrap_insight")
    assert _has_binding(DailyWorkspaceScreen, "1", "focus_list_panel")
    assert _has_binding(DailyWorkspaceScreen, "2", "focus_detail_panel")
    assert _has_binding(DailyWorkspaceScreen, "3", "focus_wrap_panel")


def test_apply_workspace_state_focuses_list_after_loading(monkeypatch) -> None:
    """Workspace should focus the list so users can navigate immediately."""
    screen = DailyWorkspaceScreen()
    focused = {"called": False}

    class DummyStatic:
        def update(self, _value) -> None:
            return

    class DummyOptionList:
        highlighted = 0
        option_count = 1

        def clear_options(self) -> None:
            return

        def add_option(self, _option) -> None:
            return

        def action_first(self) -> None:
            self.highlighted = 0

        def focus(self) -> None:
            focused["called"] = True

    widgets = {
        "#ops-status-text": DummyStatic(),
        "#daily-title": DummyStatic(),
        "#daily-subtitle": DummyStatic(),
        "#daily-section-title": DummyStatic(),
        "#daily-summary": DummyStatic(),
        "#daily-detail": DummyStatic(),
        "#daily-wrap": DummyStatic(),
        "#daily-insight": DummyStatic(),
        "#daily-list": DummyOptionList(),
    }

    monkeypatch.setattr(DailyWorkspaceScreen, "is_mounted", property(lambda self: True))
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(
        {
            "needs_plan": True,
            "top_items": [],
            "bonus_items": [],
            "candidates": {
                "must_address": [Item(id="1", type="action", title="Due", status="active")],
                "inbox": [],
                "ready_actions": [],
                "suggested": [],
            },
        }
    )

    assert focused["called"] is True


def test_apply_workspace_state_highlights_first_candidate(monkeypatch) -> None:
    """Planning mode should initialize selection on the first candidate."""
    screen = DailyWorkspaceScreen()
    state = {"highlighted": None}

    class DummyStatic:
        def update(self, _value) -> None:
            return

    class DummyOptionList:
        highlighted = None
        option_count = 1

        def clear_options(self) -> None:
            return

        def add_option(self, _option) -> None:
            return

        def action_first(self) -> None:
            self.highlighted = 0
            state["highlighted"] = self.highlighted

        def focus(self) -> None:
            return

    widgets = {
        "#ops-status-text": DummyStatic(),
        "#daily-title": DummyStatic(),
        "#daily-subtitle": DummyStatic(),
        "#daily-section-title": DummyStatic(),
        "#daily-summary": DummyStatic(),
        "#daily-detail": DummyStatic(),
        "#daily-wrap": DummyStatic(),
        "#daily-insight": DummyStatic(),
        "#daily-list": DummyOptionList(),
    }

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(
        {
            "needs_plan": True,
            "top_items": [],
            "bonus_items": [],
            "candidates": {
                "must_address": [Item(id="1", type="action", title="Due", status="active")],
                "inbox": [],
                "ready_actions": [],
                "suggested": [],
            },
        }
    )

    assert state["highlighted"] == 0


def test_apply_workspace_state_shows_next_steps_after_plan_confirmation(
    monkeypatch,
) -> None:
    """Focus mode should persist next-step guidance in the status strip."""
    screen = DailyWorkspaceScreen()
    updates: dict[str, str] = {}

    class DummyStatic:
        def __init__(self, selector: str) -> None:
            self.selector = selector

        def update(self, value) -> None:
            updates[self.selector] = value

    class DummyOptionList:
        highlighted = 0
        option_count = 2

        def clear_options(self) -> None:
            return

        def add_option(self, _option) -> None:
            return

        def action_first(self) -> None:
            self.highlighted = 0

        def focus(self) -> None:
            return

    widgets = {
        "#ops-status-text": DummyStatic("#ops-status-text"),
        "#daily-title": DummyStatic("#daily-title"),
        "#daily-subtitle": DummyStatic("#daily-subtitle"),
        "#daily-section-title": DummyStatic("#daily-section-title"),
        "#daily-summary": DummyStatic("#daily-summary"),
        "#daily-detail": DummyStatic("#daily-detail"),
        "#daily-wrap": DummyStatic("#daily-wrap"),
        "#daily-insight": DummyStatic("#daily-insight"),
        "#daily-list": DummyOptionList(),
    }

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(
        {
            "needs_plan": False,
            "top_items": [Item(id="top-1", type="action", title="Top", status="active")],
            "bonus_items": [
                Item(id="bonus-1", type="action", title="Bonus", status="active")
            ],
            "candidates": {
                "must_address": [],
                "inbox": [],
                "ready_actions": [],
                "suggested": [],
            },
        }
    )

    assert "PLAN CONFIRMED" in updates["#ops-status-text"]
    assert "[1]" in updates["#ops-status-text"]
    assert "c" in updates["#ops-status-text"]
    assert "w" in updates["#ops-status-text"]


def test_daily_workspace_cursor_actions_route_to_option_list(monkeypatch) -> None:
    """Workspace should support j/k cursor movement through the list."""
    screen = DailyWorkspaceScreen()
    calls: list[str] = []

    class DummyOptionList:
        def action_cursor_down(self) -> None:
            calls.append("down")

        def action_cursor_up(self) -> None:
            calls.append("up")

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: DummyOptionList()
    )

    screen.action_cursor_down()
    screen.action_cursor_up()

    assert calls == ["down", "up"]


@pytest.mark.asyncio
async def test_daily_workspace_confirm_key_confirms_plan_from_focused_list() -> None:
    """Pressing the dedicated confirm key should confirm the plan."""

    screen = DailyWorkspaceScreen()
    saved: dict[str, object] = {}
    refresh_called = {"called": False}

    class FakeEngine:
        def save_daily_plan(
            self, plan_date: str, *, top_item_ids: list[str], bonus_item_ids: list[str]
        ) -> None:
            saved["plan_date"] = plan_date
            saved["top_item_ids"] = top_item_ids
            saved["bonus_item_ids"] = bonus_item_ids

    async def fake_refresh_async() -> None:
        refresh_called["called"] = True

    class DailyWorkspaceTestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield screen

    screen._engine = FakeEngine()
    screen._refresh_async = fake_refresh_async  # type: ignore[method-assign]

    app = DailyWorkspaceTestApp()
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        screen._apply_workspace_state(
            {
                "needs_plan": True,
                "top_items": [
                    Item(id="top-1", type="action", title="Top", status="active")
                ],
                "bonus_items": [
                    Item(id="bonus-1", type="action", title="Bonus", status="active")
                ],
                "candidates": {
                    "must_address": [
                        Item(
                            id="cand-1",
                            type="action",
                            title="Candidate",
                            status="active",
                        )
                    ],
                    "inbox": [],
                    "ready_actions": [],
                    "suggested": [],
                },
            }
        )
        await pilot.pause()

        await pilot.press("x")
        await pilot.pause()
        await asyncio.sleep(0)

    assert saved == {
        "plan_date": screen._plan_date,
        "top_item_ids": ["top-1"],
        "bonus_item_ids": ["bonus-1"],
    }
    assert refresh_called["called"] is True


def test_build_candidate_lines_groups_items_for_planning() -> None:
    """Planning list should keep bucket labels visible."""
    screen = DailyWorkspaceScreen()
    lines = screen._build_candidate_lines(
        {
            "must_address": [Item(id="1", type="action", title="Due", status="active")],
            "inbox": [Item(id="2", type="inbox", title="Clarify note", status="active")],
            "ready_actions": [Item(id="3", type="action", title="Ready", status="active")],
            "suggested": [Item(id="4", type="action", title="Suggested", status="active")],
        }
    )

    assert lines == [
        ("must_address:1", "[Must] Due"),
        ("inbox:2", "[Inbox] Clarify note"),
        ("ready_actions:3", "[Ready] Ready"),
        ("suggested:4", "[Suggested] Suggested"),
    ]


def test_build_plan_lines_lists_top_before_bonus() -> None:
    """Focus list should show Top 3 before Bonus items."""
    screen = DailyWorkspaceScreen()
    lines = screen._build_plan_lines(
        top_items=[Item(id="top-1", type="action", title="Top", status="active")],
        bonus_items=[Item(id="bonus-1", type="action", title="Bonus", status="active")],
    )

    assert lines == [
        ("top:top-1", "[Top 1] Top"),
        ("bonus:bonus-1", "[Bonus 1] Bonus"),
    ]


def test_render_wrap_summary_celebrates_completed_top_three() -> None:
    """Wrap summary should celebrate finishing the Top 3."""
    screen = DailyWorkspaceScreen()

    summary = screen._render_wrap_summary(
        {
            "top_total": 3,
            "top_completed": 3,
            "bonus_total": 2,
            "bonus_completed": 1,
            "all_top_completed": True,
        }
    )

    assert "Top 3 complete" in summary
    assert "Bonus: 1/2" in summary


def test_render_wrap_insight_falls_back_when_unavailable() -> None:
    """Wrap insight area should degrade gracefully when AI insight is unavailable."""
    screen = DailyWorkspaceScreen()

    assert screen._render_wrap_insight(None) == "AI insight unavailable."
