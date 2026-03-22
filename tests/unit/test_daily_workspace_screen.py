"""Unit tests for the daily workspace screen."""

import asyncio
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import OptionList, Static

from flow.core.focus import CalendarAvailability
from flow.database.vector_store import VectorHit
from flow.models import Item, Resource
from flow.tui.common.widgets.quick_capture_dialog import QuickCaptureDialog
from flow.tui.common.widgets.top_three_replacement_dialog import (
    TopThreeReplacementDialog,
)
from flow.tui.screens.daily_workspace.daily_workspace import DailyWorkspaceScreen


class _DummyStatic:
    def __init__(self, selector: str) -> None:
        self.selector = selector
        self.value = ""

    def update(self, value: object) -> None:
        self.value = str(value)


class _DummyOptionList:
    def __init__(self) -> None:
        self.highlighted: int | None = None
        self.focused = False
        self.options: list[Any] = []

    @property
    def option_count(self) -> int:
        return len(self.options)

    def clear_options(self) -> None:
        self.options.clear()
        self.highlighted = None

    def add_option(self, option: Any) -> None:
        self.options.append(option)

    def action_first(self) -> None:
        for index, option in enumerate(self.options):
            if not getattr(option, "disabled", False):
                self.highlighted = index
                return

    def focus(self) -> None:
        self.focused = True

    def action_cursor_down(self) -> None:
        if self.highlighted is None:
            if self.options:
                self.highlighted = 0
            return
        if not self.options:
            return
        index = self.highlighted
        while index < len(self.options) - 1:
            index += 1
            if not getattr(self.options[index], "disabled", False):
                self.highlighted = index
                return

    def action_cursor_up(self) -> None:
        if self.highlighted is None:
            if self.options:
                self.highlighted = 0
            return
        index = self.highlighted
        while index > 0:
            index -= 1
            if not getattr(self.options[index], "disabled", False):
                self.highlighted = index
                return

    def get_option_at_index(self, index: int) -> Any:
        return self.options[index]


def _option_prompts(options: list[Any]) -> list[str]:
    return [str(option.prompt) for option in options]


def _screen_widgets() -> dict[str, Any]:
    selectors = [
        "#ops-status-text",
        "#daily-title",
        "#daily-subtitle",
        "#daily-section-title",
        "#daily-summary",
        "#daily-detail",
        "#daily-recap",
        "#daily-insight",
        "#daily-list",
        "#candidates-pane-title",
        "#candidates-pane-status",
        "#top-draft-pane-title",
        "#top-draft-pane-status",
        "#top-draft-content",
        "#bonus-draft-pane-title",
        "#bonus-draft-pane-status",
        "#bonus-draft-content",
        "#today-pane-title",
        "#today-pane-status",
        "#today-content",
        "#detail-pane-title",
        "#detail-pane-status",
        "#detail-content",
        "#recap-pane-title",
        "#recap-pane-status",
        "#recap-content",
        "#unplanned-list",
    ]
    widgets: dict[str, Any] = {selector: _DummyStatic(selector) for selector in selectors}
    widgets["#daily-list"] = _DummyOptionList()
    widgets["#unplanned-list"] = _DummyOptionList()
    return widgets


def _state_with_candidates() -> dict[str, object]:
    return {
        "needs_plan": True,
        "top_items": [
            Item(id="cand-1", type="action", title="Draft launch brief", status="active"),
            Item(id="cand-2", type="action", title="Review blockers", status="active"),
        ],
        "bonus_items": [
            Item(id="cand-3", type="action", title="Tidy backlog", status="active")
        ],
        "candidates": {
            "must_address": [
                Item(
                    id="cand-1",
                    type="action",
                    title="Draft launch brief",
                    status="active",
                )
            ],
            "inbox": [
                Item(
                    id="cand-2",
                    type="inbox",
                    title="Review blockers",
                    status="active",
                )
            ],
            "ready_actions": [
                Item(id="cand-3", type="action", title="Tidy backlog", status="active")
            ],
            "suggested": [
                Item(id="cand-4", type="action", title="Prep follow-up", status="active")
            ],
        },
    }


def _confirmed_state() -> dict[str, object]:
    return {
        "needs_plan": False,
        "top_items": [
            Item(id="top-1", type="action", title="Draft launch brief", status="active"),
            Item(id="top-2", type="action", title="Review blockers", status="active"),
        ],
        "bonus_items": [
            Item(id="bonus-1", type="action", title="Tidy backlog", status="active")
        ],
        "candidates": {
            "must_address": [],
            "inbox": [],
            "ready_actions": [],
            "suggested": [],
        },
        "unplanned_work": {
            "inbox": [
                Item(id="inbox-1", type="inbox", title="Inbox follow-up", status="active")
            ],
            "next_actions": [
                Item(
                    id="next-1",
                    type="action",
                    title="Ping designer",
                    status="active",
                )
            ],
            "project_tasks": [
                Item(
                    id="project-task-1",
                    type="action",
                    title="Prep rollout notes",
                    status="active",
                    parent_id="project-1",
                )
            ],
        },
    }


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


def test_daily_workspace_screen_exposes_plan_focus_and_recap_bindings() -> None:
    """Workspace should expose the primary planning and execution actions."""
    assert _has_binding(DailyWorkspaceScreen, "t", "add_to_top")
    assert _has_binding(DailyWorkspaceScreen, "b", "add_to_bonus")
    assert _has_binding(DailyWorkspaceScreen, "f", "recommend_focus_item")
    assert _has_binding(DailyWorkspaceScreen, "n", "new_task")
    assert _has_binding(DailyWorkspaceScreen, "x", "confirm_plan")
    assert _has_binding(DailyWorkspaceScreen, "c", "complete_planned_item")
    assert _has_binding(DailyWorkspaceScreen, "w", "show_daily_recap")
    assert _has_binding(DailyWorkspaceScreen, "I", "generate_recap_insight")
    assert _has_binding(DailyWorkspaceScreen, "1", "focus_list_panel")
    assert _has_binding(DailyWorkspaceScreen, "2", "focus_detail_panel")
    assert _has_binding(DailyWorkspaceScreen, "3", "focus_recap_panel")


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
        "#daily-recap": DummyStatic(),
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
        "#daily-recap": DummyStatic(),
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
        "#daily-recap": DummyStatic("#daily-recap"),
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


@pytest.mark.asyncio
async def test_confirmed_recap_focus_keeps_list_navigation_active() -> None:
    """Pressing 3 in confirmed state should focus the unplanned list and keep j/k active there."""

    screen = DailyWorkspaceScreen()

    class DailyWorkspaceTestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield screen

    app = DailyWorkspaceTestApp()
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        screen._apply_workspace_state(_confirmed_state())
        await pilot.pause()

        today_list = screen.query_one("#daily-list", OptionList)
        unplanned_list = screen.query_one("#unplanned-list", OptionList)
        assert app.focused is today_list
        assert today_list.highlighted == 0

        await pilot.press("3")
        await pilot.pause()

        assert screen._draft_focus == "recap"
        assert app.focused is unplanned_list
        assert unplanned_list.highlighted == 1
        assert str(unplanned_list.get_option_at_index(1).id) == "inbox:inbox-1"

        await pilot.press("j")
        await pilot.pause()

        assert unplanned_list.highlighted == 3

        await pilot.press("k")
        await pilot.pause()

        assert unplanned_list.highlighted == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["w", "x"])
async def test_startup_recap_gate_acknowledgement_routes_into_today(
    monkeypatch, key: str
) -> None:
    """Acknowledging the startup recap gate should continue directly into today's workspace."""

    class FakeDate:
        @classmethod
        def today(cls) -> Any:
            class _Today:
                def isoformat(self) -> str:
                    return "2026-03-22"

            return _Today()

    class FakeEngine:
        def __init__(self) -> None:
            self.recapped_dates: list[str] = []

        def get_daily_workspace_state(self, plan_date: str) -> dict[str, object]:
            if plan_date == "2026-03-08":
                return _confirmed_state()
            if plan_date == "2026-03-22":
                return _state_with_candidates()
            raise AssertionError(f"unexpected plan_date: {plan_date}")

        def get_daily_recap_summary(self, plan_date: str) -> dict[str, object]:
            if plan_date == "2026-03-08":
                return {
                    "top_total": 2,
                    "top_completed": 1,
                    "bonus_total": 1,
                    "bonus_completed": 0,
                    "all_top_completed": False,
                    "headline": "Solid day",
                    "coaching_feedback": "Close the loop before starting a new day.",
                    "completed_top_items": [
                        {"id": "top-1", "title": "Draft launch brief"}
                    ],
                    "completed_bonus_items": [],
                    "open_planned_items": [
                        {"id": "top-2", "title": "Review blockers"}
                    ],
                }
            if plan_date == "2026-03-22":
                return {
                    "top_total": 0,
                    "top_completed": 0,
                    "bonus_total": 0,
                    "bonus_completed": 0,
                    "all_top_completed": False,
                    "headline": "Daily Recap",
                    "coaching_feedback": "Recap will fill in as you complete planned work.",
                    "completed_top_items": [],
                    "completed_bonus_items": [],
                    "open_planned_items": [],
                }
            raise AssertionError(f"unexpected recap plan_date: {plan_date}")

        def mark_daily_plan_recapped(self, plan_date: str) -> None:
            self.recapped_dates.append(plan_date)

        def get_task_detail_resources(
            self, _item_id: str, _item_title: str
        ) -> dict[str, list[Any]]:
            return {"tag_resources": [], "semantic_resources": []}

    class DailyWorkspaceTestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield screen

    monkeypatch.setattr(
        "flow.tui.screens.daily_workspace.daily_workspace.date", FakeDate
    )

    screen = DailyWorkspaceScreen(plan_date="2026-03-08", start_in_recap=True)
    fake_engine = FakeEngine()
    screen._engine = fake_engine

    app = DailyWorkspaceTestApp()
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        assert str(screen.query_one("#daily-title", Static).renderable) == "Daily Recap"

        await pilot.press(key)
        await pilot.pause()
        await asyncio.sleep(0)
        await pilot.pause()

        assert fake_engine.recapped_dates == ["2026-03-08"]
        assert screen._plan_date == "2026-03-22"
        assert screen._startup_recap_gate is False
        assert screen._show_recap_summary is False
        assert str(screen.query_one("#daily-title", Static).renderable) == "Plan Today"
        assert "2026-03-22" in str(screen.query_one("#daily-subtitle", Static).renderable)


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


def test_apply_workspace_state_renders_visible_top_and_bonus_drafts(monkeypatch) -> None:
    """Planning mode should show explicit draft contents, not only counts."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())

    assert "Draft launch brief" in widgets["#top-draft-content"].value
    assert "Review blockers" in widgets["#top-draft-content"].value
    assert "Tidy backlog" in widgets["#bonus-draft-content"].value


def test_apply_workspace_state_empty_candidates_mentions_new_task(monkeypatch) -> None:
    """Planning mode should surface new-task guidance when no candidates are available."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(
        {
            "needs_plan": True,
            "top_items": [],
            "bonus_items": [],
            "candidates": {
                "must_address": [],
                "inbox": [],
                "ready_actions": [],
                "suggested": [],
            },
        }
    )

    assert "n" in widgets["#candidates-pane-status"].value.lower()
    assert "new task" in widgets["#detail-content"].value.lower()


def test_daily_workspace_new_task_action_opens_quick_capture_dialog(monkeypatch) -> None:
    """Daily workspace should always allow inline quick capture."""
    screen = DailyWorkspaceScreen()
    pushes: list[tuple[object, object | None]] = []

    class _FakeApp:
        def push_screen(self, dialog: object, callback: object | None = None) -> None:
            pushes.append((dialog, callback))

    monkeypatch.setattr(DailyWorkspaceScreen, "app", property(lambda self: _FakeApp()))

    screen.action_new_task()

    assert len(pushes) == 1
    assert isinstance(pushes[0][0], QuickCaptureDialog)
    assert callable(pushes[0][1])


def test_apply_workspace_state_shows_focused_item_planning_status(monkeypatch) -> None:
    """Planning detail pane should describe the focused item's current bucket."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    widgets["#daily-list"].highlighted = 0
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())

    assert "Top 3 #1" in widgets["#detail-content"].value


def test_remove_selected_top_item_updates_draft_content(monkeypatch) -> None:
    """Removing from Top 3 should update both state and visible draft pane."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())
    screen._draft_focus = "top"
    widgets["#daily-list"].highlighted = 0

    screen.action_remove_selected_draft_item()

    assert [item.id for item in screen._top_items] == ["cand-2"]
    assert "Draft launch brief" not in widgets["#top-draft-content"].value


def test_remove_selected_bonus_item_updates_draft_content(monkeypatch) -> None:
    """Removing from Bonus should update both state and visible draft pane."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())
    screen._draft_focus = "bonus"
    widgets["#daily-list"].highlighted = 0

    screen.action_remove_selected_draft_item()

    assert screen._bonus_items == []
    assert "Tidy backlog" not in widgets["#bonus-draft-content"].value


def test_planning_add_to_draft_keeps_candidates_focused(monkeypatch) -> None:
    """Planning-mode adds should update drafts without stealing focus from Candidates."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())

    widgets["#daily-list"].highlighted = 1
    screen.action_add_to_top()

    assert screen._draft_focus == "candidates"
    assert widgets["#daily-list"].focused is True
    assert widgets["#daily-list"].highlighted == 1
    assert [item.id for item in screen._top_items] == ["cand-1", "cand-2"]

    widgets["#daily-list"].highlighted = 3
    screen.action_add_to_bonus()

    assert screen._draft_focus == "candidates"
    assert widgets["#daily-list"].focused is True
    assert widgets["#daily-list"].highlighted == 3
    assert [item.id for item in screen._bonus_items] == ["cand-3", "cand-4"]


def test_planning_add_to_bonus_rejects_item_already_in_top_by_id(monkeypatch) -> None:
    """Planning-mode add should not duplicate a task into Bonus when it is already in Top 3."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())

    widgets["#daily-list"].highlighted = 0
    screen.action_add_to_bonus()

    assert [item.id for item in screen._top_items] == ["cand-1", "cand-2"]
    assert [item.id for item in screen._bonus_items] == ["cand-3"]


def test_promote_selected_bonus_item_into_top_draft(monkeypatch) -> None:
    """Promoting Bonus work should move it into the ordered Top 3 draft."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())
    screen._draft_focus = "bonus"
    widgets["#daily-list"].highlighted = 0

    screen.action_promote_bonus_item()

    assert [item.id for item in screen._top_items] == ["cand-1", "cand-2", "cand-3"]
    assert screen._bonus_items == []
    assert "Tidy backlog" in widgets["#top-draft-content"].value


def test_demote_selected_top_item_into_bonus_draft(monkeypatch) -> None:
    """Demoting Top 3 work should move it into Bonus."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())
    screen._draft_focus = "top"
    widgets["#daily-list"].highlighted = 1

    screen.action_demote_top_item()

    assert [item.id for item in screen._top_items] == ["cand-1"]
    assert [item.id for item in screen._bonus_items] == ["cand-3", "cand-2"]
    assert "Review blockers" in widgets["#bonus-draft-content"].value


def test_reorder_top_items_updates_visible_slot_order(monkeypatch) -> None:
    """Reordering Top 3 should preserve slot semantics in the draft pane."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_state_with_candidates())
    screen._draft_focus = "top"
    widgets["#daily-list"].highlighted = 1

    screen.action_move_top_item_up()

    assert [item.id for item in screen._top_items] == ["cand-2", "cand-1"]
    first_slot = widgets["#top-draft-content"].value.splitlines()[0]
    assert "Review blockers" in first_slot


def test_confirmed_state_renders_today_detail_and_grouped_unplanned_work(
    monkeypatch,
) -> None:
    """Confirmed state should hide planning panes and render grouped unplanned rows in pane 3."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    class_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(
        screen,
        "_set_classes",
        lambda selector, class_name, enabled: class_calls.append(
            (selector, class_name, enabled)
        ),
    )

    screen._apply_workspace_state(_confirmed_state())

    assert widgets["#candidates-pane-title"].value == "[1] Today"
    assert widgets["#detail-pane-title"].value == "[2] Task Detail"
    assert widgets["#recap-pane-title"].value == "[3] Unplanned Work"
    assert "t" in widgets["#ops-status-text"].value.lower()
    assert "b" in widgets["#ops-status-text"].value.lower()
    assert "d" in widgets["#ops-status-text"].value.lower()
    assert ("#top-draft-pane", "-hidden", True) in class_calls
    assert ("#bonus-draft-pane", "-hidden", True) in class_calls
    assert ("#today-pane", "-hidden", True) in class_calls
    assert widgets["#recap-content"].value == ""
    assert "Daily Recap" not in widgets["#recap-pane-status"].value
    assert [str(option.id) for option in widgets["#daily-list"].options] == [
        "top:top-1",
        "top:top-2",
        "bonus:bonus-1",
    ]
    assert [str(option.id) for option in widgets["#unplanned-list"].options] == [
        "header:inbox",
        "inbox:inbox-1",
        "header:next_actions",
        "next_actions:next-1",
        "header:project_tasks",
        "project_tasks:project-task-1",
    ]
    assert _option_prompts(widgets["#unplanned-list"].options) == [
        "Inbox (1)",
        "Inbox follow-up",
        "Next Actions (1)",
        "Ping designer",
        "Project Tasks (1)",
        "Prep rollout notes",
    ]
    assert widgets["#unplanned-list"].options[0].disabled is True
    assert widgets["#unplanned-list"].options[2].disabled is True
    assert widgets["#unplanned-list"].options[4].disabled is True
    assert widgets["#unplanned-list"].highlighted == 1


def test_confirmed_recap_focus_targets_unplanned_list(monkeypatch) -> None:
    """Confirmed recap focus should target the dedicated unplanned-work list."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_confirmed_state())
    screen.action_focus_recap_panel()

    assert screen._draft_focus == "recap"
    assert widgets["#unplanned-list"].focused is True
    assert widgets["#daily-list"].focused is True

    screen.action_focus_list_panel()

    assert screen._draft_focus == "today"
    assert widgets["#daily-list"].focused is True


def test_confirmed_state_detail_follows_planned_and_unplanned_selection(
    monkeypatch,
) -> None:
    """Confirmed detail should update when switching between planned and unplanned work."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_confirmed_state())

    assert "Current bucket: Top 3 #1" in widgets["#detail-content"].value

    screen._draft_focus = "recap"
    widgets["#unplanned-list"].highlighted = 1
    screen._refresh_supporting_panes()

    assert "Inbox follow-up" in widgets["#detail-content"].value
    assert "Unplanned source: Inbox" in widgets["#detail-content"].value


def test_recommend_focus_item_highlights_calendar_aware_confirmed_item(
    monkeypatch,
) -> None:
    """Confirmed focus action should use the calendar-aware recommendation result."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()

    class FakeEngine:
        def get_calendar_availability(self) -> CalendarAvailability:
            return CalendarAvailability(
                available=True,
                next_free_window_minutes=30,
                minutes_until_next_event=30,
            )

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    screen._engine = FakeEngine()

    state = _confirmed_state()
    state["top_items"] = [
        Item(
            id="top-long",
            type="action",
            title="Draft launch brief",
            status="active",
            estimated_duration=45,
        ),
        Item(
            id="top-fit",
            type="action",
            title="Review blockers",
            status="active",
            estimated_duration=20,
        ),
    ]
    state["bonus_items"] = [
        Item(
            id="bonus-1",
            type="action",
            title="Tidy backlog",
            status="active",
            estimated_duration=15,
        )
    ]
    screen._apply_workspace_state(state)
    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 3
    widgets["#daily-list"].highlighted = 2

    screen.action_recommend_focus_item()

    assert screen._draft_focus == "today"
    assert widgets["#daily-list"].highlighted == 1
    assert "Current bucket: Top 3 #2" in widgets["#detail-content"].value
    assert "30m" in widgets["#detail-pane-status"].value


def test_confirmed_focus_action_never_recommends_unplanned_work(
    monkeypatch,
) -> None:
    """Recommendation should be chosen only from confirmed Top 3 and Bonus items."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    state = _confirmed_state()
    state["top_items"] = []
    state["bonus_items"] = [
        Item(id="bonus-1", type="action", title="Tidy backlog", status="active")
    ]
    screen._apply_workspace_state(state)
    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1

    screen.action_recommend_focus_item()

    assert screen._draft_focus == "today"
    assert widgets["#daily-list"].highlighted == 0
    assert "Tidy backlog" in widgets["#detail-content"].value
    assert "Inbox follow-up" not in widgets["#detail-content"].value


def test_recommend_focus_item_reports_when_no_planned_items_remain(
    monkeypatch,
) -> None:
    """Recommendation should surface an explicit empty state once planned work is exhausted."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    notifications: list[str] = []
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(screen, "notify", lambda message, **_kwargs: notifications.append(message))
    screen._engine = type(
        "FakeEngine",
        (),
        {
            "get_calendar_availability": staticmethod(
                lambda: CalendarAvailability(
                    available=False,
                    next_free_window_minutes=None,
                    minutes_until_next_event=None,
                )
            )
        },
    )()

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-done", type="action", title="Done top", status="done"),
    ]
    state["bonus_items"] = [
        Item(id="bonus-done", type="action", title="Done bonus", status="done"),
    ]
    screen._apply_workspace_state(state)

    screen.action_recommend_focus_item()

    assert notifications == ["No active confirmed-plan items to recommend."]
    assert screen._draft_focus == "today"


def test_confirmed_state_adds_and_removes_items_without_reentering_planning(
    monkeypatch,
) -> None:
    """Confirmed state should ask which bucket to use before adding unplanned work back in."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    pushes: list[tuple[object, object | None]] = []

    class _FakeApp:
        def push_screen(self, dialog: object, callback: object | None = None) -> None:
            pushes.append((dialog, callback))

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(DailyWorkspaceScreen, "app", property(lambda self: _FakeApp()))

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active")
    ]
    state["bonus_items"] = []
    screen._apply_workspace_state(state)

    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1
    screen.action_add_to_top()

    assert len(pushes) == 1
    assert pushes[0][0].__class__.__name__ == "DailyWorkspacePlanBucketDialog"
    callback = pushes[0][1]
    assert callable(callback)
    callback({"bucket": "bonus"})

    assert [item.id for item in screen._top_items] == ["top-1"]
    assert [item.id for item in screen._bonus_items] == ["inbox-1"]
    assert screen._unplanned_groups["inbox"] == []


def test_confirmed_focus_recommendation_highlights_recommended_top_item(
    monkeypatch,
) -> None:
    """Confirmed focus action should highlight the next recommended planned item."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_confirmed_state())
    widgets["#daily-list"].highlighted = 2

    screen.action_recommend_focus_item()

    assert screen._draft_focus == "today"
    assert widgets["#daily-list"].highlighted == 0
    assert widgets["#daily-list"].focused is True


def test_confirmed_focus_recommendation_ignores_unplanned_selection(
    monkeypatch,
) -> None:
    """Confirmed focus action must never recommend unplanned work."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_confirmed_state())
    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1

    screen.action_recommend_focus_item()

    assert screen._draft_focus == "today"
    assert widgets["#daily-list"].highlighted == 0
    assert widgets["#unplanned-list"].highlighted == 1


def test_confirmed_focus_recommendation_reports_when_plan_is_exhausted(
    monkeypatch,
) -> None:
    """Confirmed focus action should report when no active planned items remain."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    notifications: list[str] = []
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(
        screen, "notify", lambda message, **_kwargs: notifications.append(message)
    )

    exhausted_state = _confirmed_state()
    exhausted_state["top_items"] = [
        Item(id="top-done", type="action", title="Done top", status="done")
    ]
    exhausted_state["bonus_items"] = [
        Item(id="bonus-done", type="action", title="Done bonus", status="done")
    ]
    screen._apply_workspace_state(exhausted_state)

    screen.action_recommend_focus_item()

    assert notifications == ["No active confirmed-plan items to recommend."]
    assert widgets["#daily-list"].highlighted == 0


def test_confirmed_remove_returns_item_to_original_unplanned_list_without_switching_focus(
    monkeypatch,
) -> None:
    """Confirmed remove should restore the task to its source group while keeping Today active."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(_confirmed_state())

    widgets["#daily-list"].highlighted = 1
    screen.action_remove_selected_draft_item()

    assert screen._draft_focus == "today"
    assert [str(option.id) for option in widgets["#unplanned-list"].options] == [
        "header:inbox",
        "inbox:inbox-1",
        "header:next_actions",
        "next_actions:next-1",
        "next_actions:top-2",
        "header:project_tasks",
        "project_tasks:project-task-1",
    ]


def test_confirmed_unplanned_delete_archives_selected_item(monkeypatch) -> None:
    """Confirmed unplanned delete should archive the selected item and keep recap active."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    deleted: list[str] = []
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    class FakeEngine:
        def two_min_delete(self, item_id: str) -> None:
            deleted.append(item_id)

    screen._engine = FakeEngine()
    screen._apply_workspace_state(_confirmed_state())

    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1

    screen.action_remove_selected_draft_item()

    assert deleted == ["inbox-1"]
    assert screen._draft_focus == "recap"
    assert widgets["#unplanned-list"].focused is True
    assert [str(option.id) for option in widgets["#unplanned-list"].options] == [
        "header:inbox",
        "header:next_actions",
        "next_actions:next-1",
        "header:project_tasks",
        "project_tasks:project-task-1",
    ]
    assert widgets["#unplanned-list"].highlighted == 2


def test_confirmed_remove_switches_to_unplanned_and_list_navigation_recovers(
    monkeypatch,
) -> None:
    """Confirmed today navigation should stay on the Today list after removal."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active"),
        Item(id="top-2", type="action", title="Review blockers", status="active"),
    ]
    state["bonus_items"] = [
        Item(id="bonus-1", type="action", title="Tidy backlog", status="active")
    ]
    screen._apply_workspace_state(state)

    widgets["#daily-list"].highlighted = 1
    screen.action_remove_selected_draft_item()

    assert screen._draft_focus == "today"
    assert [str(option.id) for option in widgets["#daily-list"].options] == [
        "top:top-1",
        "bonus:bonus-1",
    ]
    assert widgets["#daily-list"].highlighted == 0

    screen.action_cursor_down()

    assert widgets["#daily-list"].highlighted == 1


def test_confirmed_state_preserves_reorder_promote_demote_and_complete(
    monkeypatch,
) -> None:
    """Confirmed state should keep core plan-editing and completion actions active."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    completed: list[str] = []
    refresh_called = {"called": False}
    saved: list[dict[str, object]] = []

    class FakeEngine:
        def save_daily_plan(
            self, plan_date: str, *, top_item_ids: list[str], bonus_item_ids: list[str]
        ) -> None:
            saved.append(
                {
                    "plan_date": plan_date,
                    "top_item_ids": top_item_ids,
                    "bonus_item_ids": bonus_item_ids,
                }
            )

        def complete_item(self, item_id: str) -> None:
            completed.append(item_id)

    async def fake_refresh_async() -> None:
        refresh_called["called"] = True

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    screen._engine = FakeEngine()
    screen._refresh_async = fake_refresh_async  # type: ignore[method-assign]

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active"),
        Item(id="top-2", type="action", title="Review blockers", status="active"),
    ]
    state["bonus_items"] = [
        Item(id="bonus-1", type="action", title="Tidy backlog", status="active")
    ]
    screen._apply_workspace_state(state)

    widgets["#daily-list"].highlighted = 1
    screen.action_move_top_item_up()
    assert [item.id for item in screen._top_items] == ["top-2", "top-1"]

    widgets["#daily-list"].highlighted = 0
    screen.action_move_top_item_down()
    assert [item.id for item in screen._top_items] == ["top-1", "top-2"]

    widgets["#daily-list"].highlighted = 0
    screen.action_demote_top_item()
    assert [item.id for item in screen._top_items] == ["top-2"]
    assert [item.id for item in screen._bonus_items] == ["bonus-1", "top-1"]

    widgets["#daily-list"].highlighted = 1
    screen.action_promote_bonus_item()
    assert [item.id for item in screen._top_items] == ["top-2", "bonus-1"]
    assert [item.id for item in screen._bonus_items] == ["top-1"]

    widgets["#daily-list"].highlighted = 0
    screen.action_complete_planned_item()

    assert completed == ["top-2"]
    assert saved[-1] == {
        "plan_date": screen._plan_date,
        "top_item_ids": ["top-2", "bonus-1"],
        "bonus_item_ids": ["top-1"],
    }
    assert refresh_called["called"] is True


def test_confirmed_add_to_top_opens_replacement_chooser_when_top_three_is_full(
    monkeypatch,
) -> None:
    """Confirmed unplanned add should first ask for Top 3 vs Bonus, then handle Top 3 replacement."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    pushes: list[tuple[object, object | None]] = []

    class _FakeApp:
        def push_screen(self, dialog: object, callback: object | None = None) -> None:
            pushes.append((dialog, callback))

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(DailyWorkspaceScreen, "app", property(lambda self: _FakeApp()))

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active"),
        Item(id="top-2", type="action", title="Review blockers", status="active"),
        Item(id="top-3", type="action", title="Ship release notes", status="active"),
    ]
    state["bonus_items"] = []
    screen._apply_workspace_state(state)

    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1
    screen.action_add_to_top()

    assert len(pushes) == 1
    assert pushes[0][0].__class__.__name__ == "DailyWorkspacePlanBucketDialog"
    assert callable(pushes[0][1])


def test_confirmed_add_to_bonus_persists_updated_plan(monkeypatch) -> None:
    """Confirmed add should persist the modified plan immediately."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    pushes: list[tuple[object, object | None]] = []
    saved: dict[str, object] = {}

    class FakeEngine:
        def save_daily_plan(
            self, plan_date: str, *, top_item_ids: list[str], bonus_item_ids: list[str]
        ) -> None:
            saved["plan_date"] = plan_date
            saved["top_item_ids"] = top_item_ids
            saved["bonus_item_ids"] = bonus_item_ids

    class _FakeApp:
        def push_screen(self, dialog: object, callback: object | None = None) -> None:
            pushes.append((dialog, callback))

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(DailyWorkspaceScreen, "app", property(lambda self: _FakeApp()))
    screen._engine = FakeEngine()

    screen._apply_workspace_state(_confirmed_state())

    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1
    screen.action_add_to_bonus()

    assert len(pushes) == 1
    callback = pushes[0][1]
    assert callable(callback)

    callback({"bucket": "bonus"})

    assert saved == {
        "plan_date": screen._plan_date,
        "top_item_ids": ["top-1", "top-2"],
        "bonus_item_ids": ["bonus-1", "inbox-1"],
    }
    assert [item.id for item in screen._bonus_items] == ["bonus-1", "inbox-1"]


def test_top_three_replacement_chooser_demotes_selected_item_into_bonus(
    monkeypatch,
) -> None:
    """Chooser result should replace the selected Top 3 slot deterministically."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    pushes: list[tuple[object, object | None]] = []

    class _FakeApp:
        def push_screen(self, dialog: object, callback: object | None = None) -> None:
            pushes.append((dialog, callback))

    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    monkeypatch.setattr(DailyWorkspaceScreen, "app", property(lambda self: _FakeApp()))

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active"),
        Item(id="top-2", type="action", title="Review blockers", status="active"),
        Item(id="top-3", type="action", title="Ship release notes", status="active"),
    ]
    state["bonus_items"] = []
    screen._apply_workspace_state(state)

    screen.action_focus_recap_panel()
    widgets["#unplanned-list"].highlighted = 1
    screen.action_add_to_top()

    bucket_callback = pushes[0][1]
    assert callable(bucket_callback)
    bucket_callback({"bucket": "top"})

    assert len(pushes) == 2
    assert isinstance(pushes[1][0], TopThreeReplacementDialog)
    replacement_callback = pushes[1][1]
    assert callable(replacement_callback)
    replacement_callback({"demote_item_id": "top-2"})

    assert [item.id for item in screen._top_items] == ["top-1", "inbox-1", "top-3"]
    assert [item.id for item in screen._bonus_items] == ["top-2"]


def test_detail_pane_shows_metadata_and_resources_for_planned_selection(
    monkeypatch,
) -> None:
    """Planned detail should show concise task metadata plus related resources."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    state = _confirmed_state()
    state["top_items"] = [
        Item(
            id="top-1",
            type="action",
            title="Draft launch brief",
            status="active",
            context_tags=["launch", "docs"],
        )
    ]
    state["bonus_items"] = []
    screen._detail_resource_cache = {
        "top-1": {
            "tag_resources": [
                Resource(
                    id="resource-1",
                    content_type="text",
                    source="Launch runbook",
                    title="Launch runbook",
                    summary="Checklist for the release window and rollback plan.",
                    tags=["launch"],
                )
            ],
            "semantic_resources": [
                VectorHit(
                    resource_id="semantic-1",
                    score=0.92,
                    title="Release notes template",
                    snippet="Template for concise release notes and validation steps.",
                    source="notes/release-notes.md",
                )
            ],
        }
    }

    screen._apply_workspace_state(state)

    detail = widgets["#detail-content"].value
    assert "Current bucket: Top 3 #1" in detail
    assert "Tags: launch, docs" in detail
    assert "Resources" in detail
    assert "Launch runbook" in detail
    assert "Release notes template" in detail


def test_detail_pane_shows_concise_resources_for_unplanned_selection(
    monkeypatch,
) -> None:
    """Unplanned detail should show source metadata and concise resource snippets."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    long_summary = (
        "This is a deliberately long summary that should be trimmed so the detail pane "
        "stays readable in the confirmed workspace."
    )
    screen._detail_resource_cache = {
        "inbox-1": {
            "tag_resources": [
                Resource(
                    id="resource-2",
                    content_type="text",
                    source="Inbox note",
                    title="Inbox note",
                    summary=long_summary,
                    tags=["ops"],
                )
            ],
            "semantic_resources": [],
        }
    }

    screen._apply_workspace_state(_confirmed_state())
    screen._draft_focus = "recap"
    screen._refresh_supporting_panes()
    widgets["#daily-list"].highlighted = 0
    screen._refresh_supporting_panes()

    detail = widgets["#detail-content"].value
    assert "Inbox follow-up" in detail
    assert "Unplanned source: Inbox" in detail
    assert "Inbox note" in detail
    assert "..." in detail


def test_show_daily_recap_explicitly_replaces_unplanned_pane_content(
    monkeypatch,
) -> None:
    """Confirmed state should only show recap after the user explicitly asks for it."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    class FakeEngine:
        def get_daily_recap_summary(self, _plan_date: str) -> dict[str, object]:
            return {
                "top_total": 2,
                "top_completed": 1,
                "bonus_total": 1,
                "bonus_completed": 0,
                "all_top_completed": False,
                "headline": "Solid day",
                "coaching_feedback": "Tighten the Top 3 tomorrow.",
                "completed_top_items": [{"id": "top-1", "title": "Draft launch brief"}],
                "completed_bonus_items": [],
                "open_planned_items": [{"id": "top-2", "title": "Review blockers"}],
            }

        def mark_daily_plan_recapped(self, _plan_date: str) -> None:
            return

    screen._engine = FakeEngine()

    screen._apply_workspace_state(_confirmed_state())

    assert "Solid day" not in widgets["#recap-content"].value

    screen.action_show_daily_recap()

    assert widgets["#recap-pane-title"].value == "[3] Daily Recap"
    assert "Solid day" in widgets["#recap-content"].value
    assert widgets["#daily-recap"].value == ""
    assert "Coaching" in widgets["#recap-content"].value


def test_start_in_recap_renders_as_prior_day_recap_gate(monkeypatch) -> None:
    """Prior-day recap gate should render as recap mode, not as normal confirmed execution."""
    screen = DailyWorkspaceScreen(plan_date="2026-03-08", start_in_recap=True)
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )
    screen._recap_summary = {
        "top_total": 2,
        "top_completed": 1,
        "bonus_total": 0,
        "bonus_completed": 0,
        "all_top_completed": False,
        "headline": "Solid day",
        "coaching_feedback": "Close the loop before starting a new day.",
        "completed_top_items": [{"id": "top-1", "title": "Draft launch brief"}],
        "completed_bonus_items": [],
        "open_planned_items": [{"id": "top-2", "title": "Review blockers"}],
    }

    screen._apply_workspace_state(_confirmed_state())

    assert widgets["#daily-title"].value == "Daily Recap"
    assert "2026-03-08" in widgets["#daily-subtitle"].value
    assert "prior day" in widgets["#daily-subtitle"].value.lower()
    assert "Carry Forward" in widgets["#ops-status-text"].value
    assert "Daily Recap" in widgets["#ops-status-text"].value
    assert widgets["#candidates-pane-title"].value == "[1] Carry Forward"
    assert widgets["#candidates-pane-status"].value == "Open planned items that still need a next move"
    assert widgets["#detail-pane-title"].value == "[2] Task Detail"
    assert _option_prompts(widgets["#daily-list"].options) == [
        "[Top 1] Draft launch brief",
        "[Top 2] Review blockers",
        "[Bonus 1] Tidy backlog",
    ]
    assert "Solid day" in widgets["#recap-content"].value
    assert widgets["#daily-recap"].value == ""


def test_confirmed_state_keeps_unplanned_groups_visible_even_with_recap_summary(
    monkeypatch,
) -> None:
    """Confirmed state should not render live recap content by default."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    screen._recap_summary = {
        "top_total": 2,
        "top_completed": 1,
        "bonus_total": 1,
        "bonus_completed": 1,
        "all_top_completed": False,
        "headline": "Solid day",
        "coaching_feedback": "Keep Bonus work lighter when the Top 3 is still open.",
        "completed_top_items": [{"id": "top-1", "title": "Draft launch brief"}],
        "completed_bonus_items": [{"id": "bonus-1", "title": "Tidy backlog"}],
        "open_planned_items": [{"id": "top-2", "title": "Review blockers"}],
    }
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._apply_workspace_state(
        {
            "needs_plan": False,
            "top_items": [
                Item(id="top-2", type="action", title="Review blockers", status="active")
            ],
            "bonus_items": [],
            "candidates": {
                "must_address": [],
                "inbox": [],
                "ready_actions": [],
                "suggested": [],
            },
            "unplanned_work": {
                "inbox": [
                    Item(
                        id="inbox-1",
                        type="inbox",
                        title="Inbox follow-up",
                        status="active",
                    )
                ],
                "next_actions": [],
                "project_tasks": [],
            },
        }
    )

    recap_text = widgets["#recap-content"].value
    assert recap_text == ""
    assert "Solid day" not in recap_text
    assert "Coaching" not in recap_text
    assert [str(option.id) for option in widgets["#unplanned-list"].options] == [
        "header:inbox",
        "inbox:inbox-1",
        "header:next_actions",
        "header:project_tasks",
    ]
    assert _option_prompts(widgets["#unplanned-list"].options) == [
        "Inbox (1)",
        "Inbox follow-up",
        "Next Actions (0)",
        "Project Tasks (0)",
    ]


@pytest.mark.asyncio
async def test_refresh_async_updates_recap_pane_without_ai_path() -> None:
    """Regular refresh should keep confirmed state on grouped unplanned work."""
    screen = DailyWorkspaceScreen(plan_date="2026-03-08")

    class FakeEngine:
        def get_daily_workspace_state(self, _plan_date: str) -> dict[str, object]:
            return {
                "needs_plan": False,
                "top_items": [],
                "bonus_items": [],
                "candidates": {
                    "must_address": [],
                    "inbox": [],
                    "ready_actions": [],
                    "suggested": [],
                },
                "unplanned_work": {
                    "inbox": [],
                    "next_actions": [
                        Item(
                            id="next-1",
                            type="action",
                            title="Ping designer",
                            status="active",
                        )
                    ],
                    "project_tasks": [],
                },
            }

        def get_daily_recap_summary(self, _plan_date: str) -> dict[str, object]:
            return {
                "top_total": 1,
                "top_completed": 1,
                "bonus_total": 0,
                "bonus_completed": 0,
                "all_top_completed": True,
                "headline": "Strong day",
                "coaching_feedback": "You closed the Top 3 cleanly.",
                "completed_top_items": [{"id": "top-1", "title": "Draft launch brief"}],
                "completed_bonus_items": [],
                "open_planned_items": [],
            }

    class DailyWorkspaceTestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield screen

    screen._engine = FakeEngine()

    app = DailyWorkspaceTestApp()
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        await screen._refresh_async()
        await pilot.pause()

        recap_content = str(screen.query_one("#recap-content", Static).renderable)
        unplanned_list = screen.query_one("#unplanned-list", OptionList)
        assert recap_content == ""
        assert [str(unplanned_list.get_option_at_index(index).id) for index in range(unplanned_list.option_count)] == [
            "header:inbox",
            "header:next_actions",
            "next_actions:next-1",
            "header:project_tasks",
        ]
        assert str(unplanned_list.get_option_at_index(1).prompt) == "Next Actions (1)"
        assert str(unplanned_list.get_option_at_index(2).prompt) == "Ping designer"
        assert "Strong day" not in recap_content


def test_render_recap_summary_celebrates_completed_top_three() -> None:
    """Recap summary should celebrate finishing the Top 3."""
    screen = DailyWorkspaceScreen()

    summary = screen._render_recap_summary(
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


def test_render_recap_insight_falls_back_when_unavailable() -> None:
    """Recap insight area should degrade gracefully when AI insight is unavailable."""
    screen = DailyWorkspaceScreen()

    assert screen._render_recap_insight(None) == "AI insight unavailable."
