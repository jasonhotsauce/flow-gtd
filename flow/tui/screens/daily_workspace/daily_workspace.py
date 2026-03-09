"""Daily workspace screen: plan the day, execute it, and close it out."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.keybindings import with_global_bindings


class DailyWorkspaceScreen(FlowScreen):
    """Primary daily workspace for planning, focus, and wrap-up."""

    CSS_PATH = ["../../common/ops_tokens.tcss", "daily_workspace.tcss"]

    BINDINGS = with_global_bindings(
        ("1", "focus_list_panel", "Plan"),
        ("2", "focus_detail_panel", "Detail"),
        ("3", "focus_wrap_panel", "Wrap"),
        ("t", "add_to_top", "Top 3"),
        ("b", "add_to_bonus", "Bonus"),
        ("x", "confirm_plan", "Confirm"),
        ("c", "complete_planned_item", "Complete"),
        ("w", "show_daily_wrap", "Daily Wrap"),
        ("I", "generate_wrap_insight", "Insight"),
        Binding("i", "go_inbox", "Inbox", show=False),
        Binding("P", "go_projects", "Projects", show=False),
        Binding("r", "go_review", "Review", show=False),
    )

    def __init__(self, plan_date: str | None = None) -> None:
        super().__init__()
        self._engine = Engine()
        self._plan_date = plan_date or date.today().isoformat()
        self._mode = "plan"
        self._top_items: list = []
        self._bonus_items: list = []
        self._candidate_lookup: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="ops-status-strip"):
            yield Static("FLOW  |  Plan today, execute clearly, close the loop", id="ops-status-text")
        with Container(id="daily-header"):
            yield Static("Daily Workspace", id="daily-title")
            yield Static("", id="daily-subtitle")
        with Horizontal(id="daily-content"):
            with Vertical(id="daily-left"):
                yield Static("[1] Plan", id="daily-section-title")
                yield OptionList(id="daily-list")
            with Vertical(id="daily-right"):
                yield Static("[2] Detail", id="daily-detail-title")
                with ScrollableContainer(id="daily-detail-scroll"):
                    yield Static("", id="daily-summary")
                    yield Static("", id="daily-detail")
                yield Static("[3] Wrap", id="daily-wrap-title")
                with ScrollableContainer(id="daily-wrap-scroll"):
                    yield Static("", id="daily-wrap")
                    yield Static("", id="daily-insight")
        with Container(id="daily-help"):
            yield Static(
                "j/k: Navigate  |  1/2/3: Panels  |  t: Top 3  |  b: Bonus  |  x: Confirm  |  c: Complete  |  w: Wrap  |  I: Insight  |  Esc: Back",
                id="daily-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load workspace state asynchronously on mount."""
        asyncio.create_task(self._refresh_async())

    async def _refresh_async(self) -> None:
        state = await asyncio.to_thread(
            self._engine.get_daily_workspace_state, self._plan_date
        )
        if self.is_mounted:
            self._apply_workspace_state(state)

    def _apply_workspace_state(self, state: dict[str, object]) -> None:
        """Render either planning mode or focus mode from engine state."""
        status = self.query_one("#ops-status-text", Static)
        title = self.query_one("#daily-title", Static)
        subtitle = self.query_one("#daily-subtitle", Static)
        section = self.query_one("#daily-section-title", Static)
        summary = self.query_one("#daily-summary", Static)
        detail = self.query_one("#daily-detail", Static)
        wrap = self.query_one("#daily-wrap", Static)
        insight = self.query_one("#daily-insight", Static)
        options = self.query_one("#daily-list", OptionList)

        self._top_items = list(state["top_items"])
        self._bonus_items = list(state["bonus_items"])
        options.clear_options()
        self._candidate_lookup = {}
        wrap.update("")
        insight.update("")

        if state["needs_plan"]:
            self._mode = "plan"
            status.update(self._planning_status_text())
            title.update("Plan Today")
            subtitle.update(f"Build a realistic plan for {self._plan_date}")
            section.update("[1] Planning Candidates")
            detail.update("Select candidates, then press t or b to build Top 3 and Bonus.")
            candidates = state["candidates"]
            lines = self._build_candidate_lines(candidates)
            for option_id, label in lines:
                options.add_option(Option(label, id=option_id))
            for bucket in ("must_address", "inbox", "ready_actions", "suggested"):
                for item in candidates[bucket]:
                    self._candidate_lookup[f"{bucket}:{item.id}"] = item
            summary.update(
                f"Top 3: {len(self._top_items)}/3\nBonus: {len(self._bonus_items)}"
            )
            if options.option_count:
                options.action_first()
            options.focus()
            return

        self._mode = "focus"
        status.update(self._focus_status_text())
        title.update("Today's Focus")
        subtitle.update(f"Approved plan for {self._plan_date}")
        section.update("[1] Planned Work")
        detail.update("Complete planned work here or open Daily Wrap when the day is closing.")
        for option_id, label in self._build_plan_lines(
            top_items=self._top_items,
            bonus_items=self._bonus_items,
        ):
            options.add_option(Option(label, id=option_id))
        summary.update(
            f"Top 3: {len(self._top_items)}\nBonus: {len(self._bonus_items)}"
        )
        if options.option_count:
            options.action_first()
        options.focus()

    def _build_candidate_lines(
        self, candidates: dict[str, list[object]]
    ) -> list[tuple[str, str]]:
        """Flatten candidate groups into visible labeled lines."""
        labels = {
            "must_address": "Must",
            "inbox": "Inbox",
            "ready_actions": "Ready",
            "suggested": "Suggested",
        }
        lines: list[tuple[str, str]] = []
        for bucket in ("must_address", "inbox", "ready_actions", "suggested"):
            for item in candidates.get(bucket, []):
                lines.append((f"{bucket}:{item.id}", f"[{labels[bucket]}] {item.title}"))
        return lines

    def _build_plan_lines(
        self, *, top_items: list[object], bonus_items: list[object]
    ) -> list[tuple[str, str]]:
        """Return visible lines for Top 3 and Bonus work."""
        lines: list[tuple[str, str]] = []
        for index, item in enumerate(top_items, start=1):
            lines.append((f"top:{item.id}", f"[Top {index}] {item.title}"))
        for index, item in enumerate(bonus_items, start=1):
            lines.append((f"bonus:{item.id}", f"[Bonus {index}] {item.title}"))
        return lines

    def _render_wrap_summary(self, wrap_summary: dict[str, object]) -> str:
        """Format daily wrap summary for display."""
        top_status = f"Top 3: {wrap_summary['top_completed']}/{wrap_summary['top_total']}"
        bonus_status = (
            f"Bonus: {wrap_summary['bonus_completed']}/{wrap_summary['bonus_total']}"
        )
        if wrap_summary["all_top_completed"]:
            headline = "Top 3 complete. Today counted."
        else:
            headline = "Daily Wrap"
        return f"{headline}\n{top_status}\n{bonus_status}"

    def _render_wrap_insight(self, insight: Optional[str]) -> str:
        """Render AI insight or a stable fallback."""
        if not insight:
            return "AI insight unavailable."
        return insight

    def _planning_status_text(self) -> str:
        """Return persistent planning guidance for the status strip."""
        return "FLOW  |  Build today's plan, then press x to confirm Top 3 and Bonus"

    def _focus_status_text(self) -> str:
        """Return persistent next-step guidance after plan approval."""
        return (
            "PLAN CONFIRMED  |  Use [1] to review planned work  |  "
            "c: Complete selected item  |  w: Daily Wrap"
        )

    def action_add_to_top(self) -> None:
        """Add the selected candidate to Top 3 in planning mode."""
        if self._mode != "plan":
            return
        option = self._selected_candidate()
        if option is None:
            return
        if option in self._top_items:
            return
        if len(self._top_items) >= 3:
            self.notify("Top 3 is full. Remove or replace an item first.", timeout=2)
            return
        self._top_items.append(option)
        self.query_one("#daily-summary", Static).update(
            f"Top 3: {len(self._top_items)}/3\nBonus: {len(self._bonus_items)}"
        )

    def action_add_to_bonus(self) -> None:
        """Add the selected candidate to Bonus in planning mode."""
        if self._mode != "plan":
            return
        option = self._selected_candidate()
        if option is None:
            return
        if option in self._bonus_items:
            return
        self._bonus_items.append(option)
        self.query_one("#daily-summary", Static).update(
            f"Top 3: {len(self._top_items)}/3\nBonus: {len(self._bonus_items)}"
        )

    def action_cursor_down(self) -> None:
        """Move selection down in the main list."""
        self.query_one("#daily-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move selection up in the main list."""
        self.query_one("#daily-list", OptionList).action_cursor_up()

    def action_focus_list_panel(self) -> None:
        """Focus the main planning/focus list."""
        self.query_one("#daily-list", OptionList).focus()

    def action_focus_detail_panel(self) -> None:
        """Focus the detail panel."""
        self.query_one("#daily-detail-scroll", ScrollableContainer).focus()

    def action_focus_wrap_panel(self) -> None:
        """Focus the wrap panel."""
        self.query_one("#daily-wrap-scroll", ScrollableContainer).focus()

    def _selected_candidate(self) -> object | None:
        """Return currently highlighted candidate item."""
        options = self.query_one("#daily-list", OptionList)
        idx = options.highlighted
        if idx is None:
            return None
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return None
        return self._candidate_lookup.get(str(option.id))

    def action_confirm_plan(self) -> None:
        """Persist the current draft plan and switch into focus mode."""
        if self._mode != "plan" or not self._top_items:
            return
        self._engine.save_daily_plan(
            self._plan_date,
            top_item_ids=[item.id for item in self._top_items],
            bonus_item_ids=[item.id for item in self._bonus_items],
        )
        asyncio.create_task(self._refresh_async())

    def action_complete_planned_item(self) -> None:
        """Complete the selected planned item and refresh."""
        if self._mode != "focus":
            return
        options = self.query_one("#daily-list", OptionList)
        idx = options.highlighted
        if idx is None:
            return
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return
        _, item_id = str(option.id).split(":", maxsplit=1)
        self._engine.complete_item(item_id)
        asyncio.create_task(self._refresh_async())

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Map Enter on the focused daily list to the screen's primary action."""
        if event.option_list.id != "daily-list":
            return
        if self._mode == "plan":
            self.action_confirm_plan()
            return
        self.action_complete_planned_item()

    def action_show_daily_wrap(self) -> None:
        """Render wrap summary for the current plan."""
        wrap = self._engine.get_daily_wrap_summary(self._plan_date)
        self.query_one("#daily-wrap", Static).update(self._render_wrap_summary(wrap))

    def action_generate_wrap_insight(self) -> None:
        """Generate optional AI insight for the current daily wrap."""
        asyncio.create_task(self._generate_wrap_insight_async())

    async def _generate_wrap_insight_async(self) -> None:
        insight = await asyncio.to_thread(
            self._engine.generate_daily_wrap_insight, self._plan_date
        )
        if self.is_mounted:
            self.query_one("#daily-insight", Static).update(
                self._render_wrap_insight(insight)
            )

    def action_go_inbox(self) -> None:
        """Navigate to Inbox."""
        from flow.tui.screens.inbox.inbox import InboxScreen

        self.app.push_screen(InboxScreen())

    def action_go_projects(self) -> None:
        """Navigate to Projects."""
        from flow.tui.screens.projects.projects import ProjectsScreen

        self.app.push_screen(ProjectsScreen())

    def action_go_review(self) -> None:
        """Navigate to Review."""
        from flow.tui.screens.review.review import ReviewScreen

        self.app.push_screen(ReviewScreen())
