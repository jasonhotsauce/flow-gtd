"""Unit tests for the daily workspace screen."""

import asyncio
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from flow.models import Item
from flow.tui.common.widgets.quick_capture_dialog import QuickCaptureDialog
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
        if self.options:
            self.highlighted = 0

    def focus(self) -> None:
        self.focused = True

    def action_cursor_down(self) -> None:
        return

    def action_cursor_up(self) -> None:
        return

    def get_option_at_index(self, index: int) -> Any:
        return self.options[index]


def _screen_widgets() -> dict[str, Any]:
    selectors = [
        "#ops-status-text",
        "#daily-title",
        "#daily-subtitle",
        "#daily-section-title",
        "#daily-summary",
        "#daily-detail",
        "#daily-wrap",
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
        "#wrap-pane-title",
        "#wrap-pane-status",
        "#wrap-content",
    ]
    widgets: dict[str, Any] = {selector: _DummyStatic(selector) for selector in selectors}
    widgets["#daily-list"] = _DummyOptionList()
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


def test_daily_workspace_screen_exposes_plan_focus_and_wrap_bindings() -> None:
    """Workspace should expose the primary planning and execution actions."""
    assert _has_binding(DailyWorkspaceScreen, "t", "add_to_top")
    assert _has_binding(DailyWorkspaceScreen, "b", "add_to_bonus")
    assert _has_binding(DailyWorkspaceScreen, "n", "new_task")
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
    """Confirmed state should hide planning panes and show grouped unplanned work."""
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
    assert widgets["#wrap-pane-title"].value == "[3] Unplanned Work"
    assert "t" in widgets["#ops-status-text"].value.lower()
    assert "b" in widgets["#ops-status-text"].value.lower()
    assert "d" in widgets["#ops-status-text"].value.lower()
    assert ("#top-draft-pane", "-hidden", True) in class_calls
    assert ("#bonus-draft-pane", "-hidden", True) in class_calls
    assert ("#today-pane", "-hidden", True) in class_calls
    assert "Inbox" in widgets["#wrap-content"].value
    assert "Project Tasks" in widgets["#wrap-content"].value
    assert "Daily Wrap" not in widgets["#wrap-pane-status"].value


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

    screen._draft_focus = "wrap"
    widgets["#daily-list"].highlighted = 0
    screen._refresh_supporting_panes()

    assert "Inbox follow-up" in widgets["#detail-content"].value
    assert "Unplanned source: Inbox" in widgets["#detail-content"].value


def test_confirmed_state_adds_and_removes_items_without_reentering_planning(
    monkeypatch,
) -> None:
    """Confirmed state should let users pull unplanned work in and remove planned work out."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    state = _confirmed_state()
    state["top_items"] = [
        Item(id="top-1", type="action", title="Draft launch brief", status="active")
    ]
    state["bonus_items"] = []
    screen._apply_workspace_state(state)

    screen._draft_focus = "wrap"
    screen._refresh_supporting_panes()
    widgets["#daily-list"].highlighted = 0
    screen.action_add_to_top()

    assert [item.id for item in screen._top_items] == ["top-1", "inbox-1"]
    assert screen._unplanned_groups["inbox"] == []

    widgets["#daily-list"].highlighted = 0
    screen.action_add_to_bonus()

    assert [item.id for item in screen._bonus_items] == ["next-1"]
    assert screen._unplanned_groups["next_actions"] == []

    screen._draft_focus = "today"
    screen._refresh_supporting_panes()
    widgets["#daily-list"].highlighted = 1
    screen.action_remove_selected_draft_item()

    assert [item.id for item in screen._top_items] == ["top-1"]
    assert [item.id for item in screen._unplanned_groups["inbox"]] == ["inbox-1"]


def test_confirmed_state_preserves_reorder_promote_demote_and_complete(
    monkeypatch,
) -> None:
    """Confirmed state should keep core plan-editing and completion actions active."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    completed: list[str] = []
    refresh_called = {"called": False}

    class FakeEngine:
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
    assert refresh_called["called"] is True


def test_confirmed_state_keeps_unplanned_groups_visible_even_with_wrap_summary(
    monkeypatch,
) -> None:
    """Confirmed state should not render live wrap content by default."""
    screen = DailyWorkspaceScreen()
    widgets = _screen_widgets()
    screen._wrap_summary = {
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

    wrap_text = widgets["#wrap-content"].value
    assert "Inbox" in wrap_text
    assert "Inbox follow-up" in wrap_text
    assert "Solid day" not in wrap_text
    assert "Coaching" not in wrap_text


@pytest.mark.asyncio
async def test_refresh_async_updates_wrap_pane_without_ai_path() -> None:
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

        def get_daily_wrap_summary(self, _plan_date: str) -> dict[str, object]:
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

        wrap_content = str(screen.query_one("#wrap-content", Static).renderable)
        assert "Next Actions" in wrap_content
        assert "Ping designer" in wrap_content
        assert "Strong day" not in wrap_content
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
