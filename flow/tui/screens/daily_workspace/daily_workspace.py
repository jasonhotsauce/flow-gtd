"""Daily workspace screen: plan the day, execute it, and close it out."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.database.vector_store import VectorHit
from flow.models import Item
from flow.models import Resource
from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.widgets.quick_capture_dialog import QuickCaptureDialog, QuickCaptureResult
from flow.tui.common.widgets.top_three_replacement_dialog import (
    TopThreeReplacementDialog,
)
from flow.tui.common.keybindings import with_global_bindings


class DailyWorkspaceScreen(FlowScreen):
    """Primary daily workspace for planning, focus, and wrap-up."""

    CSS_PATH = ["../../common/ops_tokens.tcss", "daily_workspace.tcss"]

    BINDINGS = with_global_bindings(
        ("1", "focus_list_panel", "Primary"),
        ("2", "focus_detail_panel", "Detail"),
        ("3", "focus_wrap_panel", "Wrap"),
        ("t", "add_to_top", "Top 3"),
        ("b", "add_to_bonus", "Bonus"),
        ("n", "new_task", "New Task"),
        ("d", "remove_selected_draft_item", "Remove"),
        ("p", "promote_bonus_item", "Promote"),
        ("m", "demote_top_item", "Demote"),
        ("K", "move_top_item_up", "Move Up"),
        ("J", "move_top_item_down", "Move Down"),
        ("x", "confirm_plan", "Confirm"),
        ("c", "complete_planned_item", "Complete"),
        ("w", "show_daily_wrap", "Daily Wrap"),
        ("I", "generate_wrap_insight", "Insight"),
        Binding("i", "go_inbox", "Inbox", show=False),
        Binding("P", "go_projects", "Projects", show=False),
        Binding("r", "go_review", "Review", show=False),
    )

    def __init__(
        self, plan_date: str | None = None, start_in_wrap: bool = False
    ) -> None:
        super().__init__()
        self._engine = Engine()
        self._plan_date = plan_date or date.today().isoformat()
        self._mode = "plan"
        self._top_items: list[Item] = []
        self._bonus_items: list[Item] = []
        self._candidate_lookup: dict[str, Item] = {}
        self._today_lookup: dict[str, Item] = {}
        self._unplanned_lookup: dict[str, Item] = {}
        self._unplanned_groups: dict[str, list[Item]] = {
            "inbox": [],
            "next_actions": [],
            "project_tasks": [],
        }
        self._draft_focus = "candidates"
        self._top_selected_index = 0
        self._bonus_selected_index = 0
        self._wrap_summary: dict[str, object] | None = None
        self._pending_top_replacement_item: Item | None = None
        self._detail_resource_cache: dict[str, dict[str, list[Resource | VectorHit]]] = {}
        self._show_wrap_summary = start_in_wrap

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="ops-status-strip"):
            yield Static("FLOW  |  Plan today, execute clearly, close the loop", id="ops-status-text")
        with Container(id="daily-header"):
            yield Static("Daily Workspace", id="daily-title")
            yield Static("", id="daily-subtitle")
        with Horizontal(id="daily-content"):
            with Vertical(id="daily-primary-column"):
                with Container(classes="daily-pane", id="candidates-pane"):
                    yield Static("[1] Candidates", id="candidates-pane-title", classes="daily-pane-title")
                    yield Static("", id="candidates-pane-status", classes="daily-pane-status")
                    yield OptionList(id="daily-list")
                with Container(classes="daily-pane", id="detail-pane"):
                    yield Static("[2] Detail", id="detail-pane-title", classes="daily-pane-title")
                    yield Static("", id="detail-pane-status", classes="daily-pane-status")
                    with ScrollableContainer(id="detail-pane-scroll", classes="daily-pane-scroll"):
                        yield Static("", id="detail-content")
                with Container(classes="daily-pane -hidden", id="today-pane"):
                    yield Static("[1] Today", id="today-pane-title", classes="daily-pane-title")
                    yield Static("", id="today-pane-status", classes="daily-pane-status")
                    with ScrollableContainer(id="today-pane-scroll", classes="daily-pane-scroll"):
                        yield Static("", id="today-content")
            with Vertical(id="daily-secondary-column"):
                with Container(classes="daily-pane", id="top-draft-pane"):
                    yield Static("Top 3 Draft", id="top-draft-pane-title", classes="daily-pane-title")
                    yield Static("", id="top-draft-pane-status", classes="daily-pane-status")
                    with ScrollableContainer(id="top-draft-pane-scroll", classes="daily-pane-scroll"):
                        yield Static("", id="top-draft-content")
                with Container(classes="daily-pane", id="bonus-draft-pane"):
                    yield Static("Bonus Draft", id="bonus-draft-pane-title", classes="daily-pane-title")
                    yield Static("", id="bonus-draft-pane-status", classes="daily-pane-status")
                    with ScrollableContainer(id="bonus-draft-pane-scroll", classes="daily-pane-scroll"):
                        yield Static("", id="bonus-draft-content")
                with Container(classes="daily-pane", id="wrap-pane"):
                    yield Static("[3] Wrap", id="wrap-pane-title", classes="daily-pane-title")
                    yield Static("", id="wrap-pane-status", classes="daily-pane-status")
                    with ScrollableContainer(id="wrap-pane-scroll", classes="daily-pane-scroll"):
                        yield Static("", id="wrap-content")
                        yield Static("", id="daily-wrap")
                        yield Static("", id="daily-insight")
                        yield Static("", id="daily-wrap-legacy", classes="-hidden")
        with Container(id="daily-help"):
            yield Static(
                "1/2/3: Primary, Detail, Wrap  |  n: New task  |  t/b: Add to draft  |  d: Remove  |  p/m: Promote or demote  |  Shift+J/K: Reorder Top 3  |  x: Confirm  |  c: Complete",
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
        wrap_summary = await asyncio.to_thread(
            self._engine.get_daily_wrap_summary, self._plan_date
        )
        if self.is_mounted:
            self._wrap_summary = wrap_summary
            self._apply_workspace_state(state)

    def _safe_query_one(self, selector: str, widget_type: type[Any]) -> Any | None:
        try:
            return self.query_one(selector, widget_type)
        except Exception:
            return None

    def _set_text(self, selector: str, value: str) -> None:
        widget = self._safe_query_one(selector, Static)
        if widget is not None:
            widget.update(value)

    def _set_classes(self, selector: str, class_name: str, enabled: bool) -> None:
        widget = self._safe_query_one(selector, Container)
        if widget is None:
            return
        if enabled:
            widget.add_class(class_name)
        else:
            widget.remove_class(class_name)

    def _pane_hint(self) -> str:
        if self._mode == "plan":
            return "Planning mode. n captures new work. t/b add from Candidates. d removes from the active draft."
        if self._draft_focus == "wrap":
            return "Confirmed state. Review unplanned work here and use t/b to pull it into today's plan."
        return "Confirmed state. Review today's plan here, complete work with c, or remove it with d."

    def _draft_bucket_status(self, item: Item) -> str:
        for index, top_item in enumerate(self._top_items, start=1):
            if top_item.id == item.id:
                return f"Top 3 #{index}"
        if any(bonus_item.id == item.id for bonus_item in self._bonus_items):
            return "Bonus"
        return "Not planned"

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

    def _build_unplanned_lines(
        self, unplanned_work: dict[str, list[Item]]
    ) -> list[tuple[str, str]]:
        """Return visible lines for grouped unplanned work."""
        labels = {
            "inbox": "Inbox",
            "next_actions": "Next",
            "project_tasks": "Project",
        }
        lines: list[tuple[str, str]] = []
        for bucket in ("inbox", "next_actions", "project_tasks"):
            for item in unplanned_work.get(bucket, []):
                lines.append((f"{bucket}:{item.id}", f"[{labels[bucket]}] {item.title}"))
        return lines

    def _render_top_draft_content(self) -> str:
        lines: list[str] = []
        for slot in range(3):
            if slot < len(self._top_items):
                marker = ">" if self._draft_focus == "top" and self._top_selected_index == slot else " "
                lines.append(f"{marker} Top 3 #{slot + 1}  {self._top_items[slot].title}")
            else:
                lines.append(f"  Slot {slot + 1} open")
        return "\n".join(lines)

    def _render_bonus_draft_content(self) -> str:
        if not self._bonus_items:
            return "  No Bonus items yet."
        lines: list[str] = []
        for index, item in enumerate(self._bonus_items, start=1):
            marker = ">" if self._draft_focus == "bonus" and self._bonus_selected_index == index - 1 else " "
            lines.append(f"{marker} Bonus {index}  {item.title}")
        return "\n".join(lines)

    def _render_today_content(self) -> str:
        lines = ["Top 3"]
        if self._top_items:
            lines.extend(f"  {index}. {item.title}" for index, item in enumerate(self._top_items, start=1))
        else:
            lines.append("  No active Top 3 items.")
        lines.append("")
        lines.append("Bonus")
        if self._bonus_items:
            lines.extend(f"  {index}. {item.title}" for index, item in enumerate(self._bonus_items, start=1))
        else:
            lines.append("  No active Bonus items.")
        return "\n".join(lines)

    def _render_unplanned_content(self) -> str:
        """Render grouped unplanned work for the confirmed-state side pane."""
        sections = (
            ("Inbox", self._unplanned_groups["inbox"]),
            ("Next Actions", self._unplanned_groups["next_actions"]),
            ("Project Tasks", self._unplanned_groups["project_tasks"]),
        )
        lines: list[str] = []
        for index, (title, items) in enumerate(sections):
            if index:
                lines.append("")
            lines.append(title)
            if items:
                lines.extend(f"  - {item.title}" for item in items)
            else:
                lines.append("  - None")
        return "\n".join(lines)

    def _render_wrap_summary(self, wrap_summary: dict[str, object]) -> str:
        """Format daily wrap summary for display."""
        headline = str(wrap_summary.get("headline") or "Daily Wrap")
        if headline == "Daily Wrap" and wrap_summary.get("all_top_completed"):
            headline = "Top 3 complete. Today counted."
        top_status = f"Top 3 completed: {wrap_summary['top_completed']}/{wrap_summary['top_total']}"
        bonus_status = f"Bonus: {wrap_summary['bonus_completed']}/{wrap_summary['bonus_total']}"
        lines = [headline, top_status, bonus_status]

        completed_top = wrap_summary.get("completed_top_items", [])
        completed_bonus = wrap_summary.get("completed_bonus_items", [])
        open_items = wrap_summary.get("open_planned_items", [])
        coaching = wrap_summary.get("coaching_feedback")

        if completed_top or completed_bonus:
            lines.append("")
            lines.append("Accomplishments")
            for item in completed_top:
                lines.append(f"  [Top] {item['title']}")
            for item in completed_bonus:
                lines.append(f"  [Bonus] {item['title']}")

        lines.append("")
        lines.append("Carry Forward")
        if open_items:
            for item in open_items:
                lines.append(f"  {item['title']}")
        else:
            lines.append("  Nothing planned is still open.")

        if coaching:
            lines.append("")
            lines.append("Coaching")
            lines.append(f"  {coaching}")

        return "\n".join(lines)

    def _render_wrap_insight(self, insight: Optional[str]) -> str:
        """Render AI insight or a stable fallback."""
        if not insight:
            return "AI insight unavailable."
        return insight

    def _planning_status_text(self) -> str:
        """Return persistent planning guidance for the status strip."""
        return (
            "FLOW  |  Build today's plan in visible Top 3 and Bonus drafts  |  "
            "t/b add, d remove, p/m rebalance, Shift+J/K reorder, x confirm"
        )

    def _focus_status_text(self) -> str:
        """Return persistent next-step guidance after plan approval."""
        return (
            "PLAN CONFIRMED  |  [1] Today  [3] Unplanned Work  |  "
            "t/b add, d remove, c complete, w wrap"
        )

    def _current_list_widget(self) -> OptionList | None:
        return self._safe_query_one("#daily-list", OptionList)

    def _selected_candidate(self) -> Item | None:
        options = self._current_list_widget()
        if options is None:
            return None
        idx = options.highlighted
        if idx is None:
            return None
        if not hasattr(options, "get_option_at_index"):
            return None
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return None
        return self._candidate_lookup.get(str(option.id))

    def _selected_option_id(self) -> str | None:
        options = self._current_list_widget()
        if options is None:
            return None
        idx = options.highlighted
        if idx is None or not hasattr(options, "get_option_at_index"):
            return None
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return None
        return str(option.id)

    def _selected_today_item(self) -> Item | None:
        options = self._current_list_widget()
        if options is None:
            return None
        idx = options.highlighted
        if idx is None:
            return None
        if not hasattr(options, "get_option_at_index"):
            return None
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return None
        return self._today_lookup.get(str(option.id))

    def _selected_today_bucket_and_index(self) -> tuple[str, int] | None:
        option_id = self._selected_option_id()
        if option_id is None:
            return None
        bucket, _, item_id = option_id.partition(":")
        if bucket == "top":
            for index, item in enumerate(self._top_items):
                if item.id == item_id:
                    return ("top", index)
        if bucket == "bonus":
            for index, item in enumerate(self._bonus_items):
                if item.id == item_id:
                    return ("bonus", index)
        return None

    def _selected_unplanned_item(self) -> Item | None:
        options = self._current_list_widget()
        if options is None:
            return None
        idx = options.highlighted
        if idx is None:
            return None
        if not hasattr(options, "get_option_at_index"):
            return None
        try:
            option = options.get_option_at_index(idx)
        except IndexError:
            return None
        return self._unplanned_lookup.get(str(option.id))

    def _current_detail_item(self) -> Item | None:
        """Return the item currently driving the detail pane."""
        if self._mode == "plan":
            if self._draft_focus == "top":
                return self._selected_top_item()
            if self._draft_focus == "bonus":
                return self._selected_bonus_item()
            return self._selected_candidate()
        if self._draft_focus == "wrap":
            return self._selected_unplanned_item()
        return self._selected_today_item()

    def _sync_draft_index_from_primary_list(self) -> None:
        options = self._current_list_widget()
        if options is None:
            return
        idx = getattr(options, "highlighted", None)
        if idx is None:
            return
        if self._draft_focus == "top" and self._top_items:
            self._top_selected_index = max(0, min(idx, len(self._top_items) - 1))
        if self._draft_focus == "bonus" and self._bonus_items:
            self._bonus_selected_index = max(0, min(idx, len(self._bonus_items) - 1))

    def _selected_top_item(self) -> Item | None:
        self._sync_draft_index_from_primary_list()
        if not self._top_items:
            return None
        index = max(0, min(self._top_selected_index, len(self._top_items) - 1))
        self._top_selected_index = index
        return self._top_items[index]

    def _selected_bonus_item(self) -> Item | None:
        self._sync_draft_index_from_primary_list()
        if not self._bonus_items:
            return None
        index = max(0, min(self._bonus_selected_index, len(self._bonus_items) - 1))
        self._bonus_selected_index = index
        return self._bonus_items[index]

    def _render_detail_content(self) -> str:
        if self._mode == "plan":
            if self._draft_focus == "top":
                selected_top = self._selected_top_item()
                if selected_top is None:
                    return "Select a candidate, then press t or b to start drafting."
                return (
                    f"{selected_top.title}\n"
                    f"Current status: {self._draft_bucket_status(selected_top)}\n"
                    "Hint: m demotes this item into Bonus. Shift+J/K reorders Top 3."
                )
            if self._draft_focus == "bonus":
                selected_bonus = self._selected_bonus_item()
                if selected_bonus is None:
                    return "Bonus draft is empty. Add a candidate with b or capture a new task with n."
                return (
                    f"{selected_bonus.title}\n"
                    "Current status: Bonus\n"
                    "Hint: p promotes this item into Top 3 if a slot is open."
                )
            selected = self._selected_candidate()
            if selected is None:
                return (
                    "No candidates yet.\n"
                    "Press n to capture a new task, then use t or b to place it into today's plan."
                )
            return (
                f"{selected.title}\n"
                f"Current status: {self._draft_bucket_status(selected)}\n"
                "Hint: n captures new work, t adds to Top 3, b adds to Bonus, x confirms the plan."
            )

        selected = self._selected_today_item()
        if self._draft_focus == "wrap":
            selected_unplanned = self._selected_unplanned_item()
            if selected_unplanned is None:
                return "Select unplanned work to review it here, then use t or b to add it back into today's plan."
            source = "Inbox"
            if selected_unplanned.parent_id is not None:
                source = "Project Tasks"
            elif selected_unplanned.type == "action":
                source = "Next Actions"
            detail = (
                f"{selected_unplanned.title}\n"
                f"Unplanned source: {source}\n"
                "Hint: t adds this to Top 3. b adds this to Bonus."
            )
            resources = self._render_detail_resources(selected_unplanned)
            if resources:
                detail = f"{detail}\n{resources}"
            return detail
        if selected is None:
            return "Plan confirmed. Today list is now active."
        detail = (
            "Plan confirmed. Today list is now active.\n"
            f"{selected.title}\n"
            f"Current bucket: {self._draft_bucket_status(selected)}\n"
            "Hint: c marks this item complete. d removes it back to unplanned work."
        )
        if selected.context_tags:
            detail = f"{detail}\nTags: {', '.join(selected.context_tags)}"
        resources = self._render_detail_resources(selected)
        if resources:
            detail = f"{detail}\n{resources}"
        return detail

    @staticmethod
    def _truncate_detail_text(value: str, limit: int = 72) -> str:
        """Keep resource copy compact for the narrow detail pane."""
        if len(value) <= limit:
            return value
        return f"{value[: limit - 3].rstrip()}..."

    def _render_detail_resources(self, item: Item) -> str:
        """Render cached detail resources for the selected item."""
        payload = self._detail_resource_cache.get(item.id)
        if not payload:
            return ""
        lines = ["", "Resources"]
        tag_resources = payload.get("tag_resources", [])
        semantic_resources = payload.get("semantic_resources", [])
        for resource in tag_resources:
            if not isinstance(resource, Resource):
                continue
            title = resource.title or resource.source
            summary = resource.summary or resource.source
            lines.append(f"  [Tag] {title}")
            lines.append(f"    {self._truncate_detail_text(summary)}")
        for hit in semantic_resources:
            if not isinstance(hit, VectorHit):
                continue
            lines.append(f"  [Semantic] {hit.title or hit.source}")
            lines.append(f"    {self._truncate_detail_text(hit.snippet or hit.source)}")
        return "\n".join(lines)

    def _schedule_detail_resource_load(self) -> None:
        """Load detail resources asynchronously for the currently selected item."""
        item = self._current_detail_item()
        if item is None or item.id in self._detail_resource_cache:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._load_detail_resources_async(item))

    async def _load_detail_resources_async(self, item: Item) -> None:
        """Fetch detail resources off the UI thread and refresh the pane if still selected."""
        payload = await asyncio.to_thread(
            self._engine.get_task_detail_resources, item.id, item.title
        )
        self._detail_resource_cache[item.id] = payload
        current_item = self._current_detail_item()
        if self.is_mounted and current_item is not None and current_item.id == item.id:
            self._set_text("#detail-content", self._render_detail_content())

    def _refresh_confirmed_list(self) -> None:
        """Refresh the shared OptionList based on the active confirmed-state pane."""
        options = self._current_list_widget()
        if options is None:
            return
        self._today_lookup = {
            f"top:{item.id}": item for item in self._top_items
        } | {
            f"bonus:{item.id}": item for item in self._bonus_items
        }
        self._unplanned_lookup = {
            f"inbox:{item.id}": item for item in self._unplanned_groups["inbox"]
        } | {
            f"next_actions:{item.id}": item
            for item in self._unplanned_groups["next_actions"]
        } | {
            f"project_tasks:{item.id}": item
            for item in self._unplanned_groups["project_tasks"]
        }
        options.clear_options()
        if self._draft_focus == "wrap":
            for option_id, label in self._build_unplanned_lines(self._unplanned_groups):
                options.add_option(Option(label, id=option_id))
        else:
            for option_id, label in self._build_plan_lines(
                top_items=self._top_items,
                bonus_items=self._bonus_items,
            ):
                options.add_option(Option(label, id=option_id))
        if options.option_count:
            options.action_first()
            options.focus()

    def _restore_to_unplanned(self, item: Item) -> None:
        """Return a removed planned item to its original open-work group."""
        if item.parent_id is not None:
            bucket = "project_tasks"
        elif item.type == "action":
            bucket = "next_actions"
        else:
            bucket = "inbox"
        if any(existing.id == item.id for existing in self._unplanned_groups[bucket]):
            return
        self._unplanned_groups[bucket].append(item)
        self._unplanned_lookup[f"{bucket}:{item.id}"] = item

    def _consume_selected_unplanned_item(self) -> Item | None:
        """Remove the selected unplanned item from its source group and return it."""
        item = self._selected_unplanned_item()
        option_id = self._selected_option_id()
        if item is None or option_id is None:
            return None
        bucket, _, _item_id = option_id.partition(":")
        if bucket not in self._unplanned_groups:
            return None
        self._unplanned_groups[bucket] = [
            existing for existing in self._unplanned_groups[bucket] if existing.id != item.id
        ]
        self._unplanned_lookup.pop(option_id, None)
        return item

    def _remove_from_unplanned_groups(self, item_id: str) -> None:
        """Remove an item from all unplanned groups by id."""
        for bucket in self._unplanned_groups:
            self._unplanned_groups[bucket] = [
                item for item in self._unplanned_groups[bucket] if item.id != item_id
            ]
            self._unplanned_lookup.pop(f"{bucket}:{item_id}", None)

    def _apply_top_three_replacement_choice(
        self, result: dict[str, str] | None
    ) -> None:
        """Replace a selected Top 3 slot with the pending unplanned item."""
        pending_item = self._pending_top_replacement_item
        self._pending_top_replacement_item = None
        if pending_item is None or not result:
            return
        demote_item_id = result.get("demote_item_id")
        if not demote_item_id:
            return
        for index, item in enumerate(self._top_items):
            if item.id != demote_item_id:
                continue
            demoted_item = self._top_items[index]
            self._top_items[index] = pending_item
            self._bonus_items.append(demoted_item)
            self._remove_from_unplanned_groups(pending_item.id)
            self._draft_focus = "today"
            self._refresh_supporting_panes()
            return

    def _refresh_supporting_panes(self) -> None:
        self._set_text(
            "#top-draft-pane-status",
            f"{len(self._top_items)}/3 committed  |  {'Active' if self._draft_focus == 'top' else 'Stable'}",
        )
        self._set_text(
            "#bonus-draft-pane-status",
            f"{len(self._bonus_items)} bonus item(s)  |  {'Active' if self._draft_focus == 'bonus' else 'Secondary'}",
        )
        self._set_text("#top-draft-content", self._render_top_draft_content())
        self._set_text("#bonus-draft-content", self._render_bonus_draft_content())
        self._set_text("#today-content", self._render_today_content())
        if self._mode == "focus":
            self._refresh_confirmed_list()
        self._set_text("#detail-pane-status", self._pane_hint())
        self._set_text("#detail-content", self._render_detail_content())
        self._schedule_detail_resource_load()
        if self._mode == "focus":
            if self._show_wrap_summary:
                if self._wrap_summary is None:
                    self._wrap_summary = {
                        "top_total": len(self._top_items),
                        "top_completed": 0,
                        "bonus_total": len(self._bonus_items),
                        "bonus_completed": 0,
                        "headline": "Daily Wrap",
                        "coaching_feedback": "Wrap will fill in as you complete planned work.",
                        "completed_top_items": [],
                        "completed_bonus_items": [],
                        "open_planned_items": [
                            {"id": item.id, "title": item.title}
                            for item in self._top_items + self._bonus_items
                        ],
                    }
                wrap_text = self._render_wrap_summary(self._wrap_summary)
                self._set_text("#wrap-pane-title", "[3] Daily Wrap")
                self._set_text("#wrap-pane-status", "Explicit wrap summary")
                self._set_text("#wrap-content", wrap_text)
                self._set_text("#daily-wrap", wrap_text)
            else:
                self._set_text("#wrap-pane-title", "[3] Unplanned Work")
                self._set_text("#wrap-pane-status", "Inbox, Next Actions, Project Tasks")
                self._set_text("#wrap-content", self._render_unplanned_content())
                self._set_text("#daily-wrap", "")
            return
        if self._wrap_summary is None:
            self._wrap_summary = {
                "top_total": len(self._top_items),
                "top_completed": 0,
                "bonus_total": len(self._bonus_items),
                "bonus_completed": 0,
                "headline": "Daily Wrap",
                "coaching_feedback": "Wrap will fill in as you complete planned work.",
                "completed_top_items": [],
                "completed_bonus_items": [],
                "open_planned_items": [
                    {"id": item.id, "title": item.title} for item in self._top_items + self._bonus_items
                ],
            }
        wrap_text = self._render_wrap_summary(self._wrap_summary)
        self._set_text("#wrap-pane-status", "Live daily wrap feedback")
        self._set_text("#wrap-content", wrap_text)
        self._set_text("#daily-wrap", wrap_text)

    def _apply_workspace_state(self, state: dict[str, object]) -> None:
        """Render either planning mode or focus mode from engine state."""
        self._top_items = list(state["top_items"])
        self._bonus_items = list(state["bonus_items"])
        if not self._bonus_items:
            self._bonus_selected_index = 0
        if not self._top_items:
            self._top_selected_index = 0

        options = self._current_list_widget()
        if options is not None:
            options.clear_options()
        self._candidate_lookup = {}
        self._today_lookup = {}
        self._unplanned_lookup = {}
        unplanned_work = state.get("unplanned_work") or {
            "inbox": [],
            "next_actions": [],
            "project_tasks": [],
        }
        self._unplanned_groups = {
            "inbox": list(unplanned_work["inbox"]),
            "next_actions": list(unplanned_work["next_actions"]),
            "project_tasks": list(unplanned_work["project_tasks"]),
        }
        self._set_text("#daily-insight", "")

        if state["needs_plan"]:
            self._mode = "plan"
            self._draft_focus = self._draft_focus if self._draft_focus in {"candidates", "top", "bonus"} else "candidates"
            candidates = state["candidates"]
            self._set_text("#ops-status-text", self._planning_status_text())
            self._set_text("#daily-title", "Plan Today")
            self._set_text("#daily-subtitle", f"Build a realistic plan for {self._plan_date}")
            self._set_text("#daily-section-title", "[1] Planning Candidates")
            self._set_text("#daily-summary", f"Top 3: {len(self._top_items)}/3\nBonus: {len(self._bonus_items)}")
            self._set_text("#candidates-pane-title", "[1] Candidates")
            if any(candidates[bucket] for bucket in ("must_address", "inbox", "ready_actions", "suggested")):
                self._set_text("#candidates-pane-status", "Must, Inbox, Ready, Suggested  |  n: New task")
            else:
                self._set_text("#candidates-pane-status", "No candidates yet  |  n: New task")
            self._set_text("#top-draft-pane-title", "Top 3 Draft")
            self._set_text("#bonus-draft-pane-title", "Bonus Draft")
            self._set_text("#today-pane-title", "Today")
            self._set_classes("#today-pane", "-hidden", True)
            self._set_classes("#candidates-pane", "-hidden", False)

            for option_id, label in self._build_candidate_lines(candidates):
                if options is not None:
                    options.add_option(Option(label, id=option_id))
            for bucket in ("must_address", "inbox", "ready_actions", "suggested"):
                for item in candidates[bucket]:
                    self._candidate_lookup[f"{bucket}:{item.id}"] = item
            if options is not None and options.option_count:
                options.action_first()
                if self._draft_focus == "candidates":
                    options.focus()
            self._refresh_supporting_panes()
            return

        self._mode = "focus"
        if self._draft_focus not in {"today", "detail", "wrap"}:
            self._draft_focus = "today"
        self._set_text("#ops-status-text", self._focus_status_text())
        self._set_text("#daily-title", "Today's Focus")
        self._set_text("#daily-subtitle", f"Approved plan for {self._plan_date}")
        self._set_text("#daily-section-title", "[1] Today")
        self._set_text("#daily-summary", f"Top 3: {len(self._top_items)}\nBonus: {len(self._bonus_items)}")
        self._set_text("#candidates-pane-title", "[1] Today")
        self._set_text("#candidates-pane-status", "Top 3 first, Bonus second")
        self._set_text("#detail-pane-title", "[2] Task Detail")
        self._set_text(
            "#wrap-pane-title",
            "[3] Daily Wrap" if self._show_wrap_summary else "[3] Unplanned Work",
        )
        self._set_classes("#top-draft-pane", "-hidden", True)
        self._set_classes("#bonus-draft-pane", "-hidden", True)
        self._set_classes("#today-pane", "-hidden", True)
        self._set_classes("#candidates-pane", "-hidden", False)
        self._today_lookup = {
            f"top:{item.id}": item for item in self._top_items
        } | {
            f"bonus:{item.id}": item for item in self._bonus_items
        }
        self._unplanned_lookup = {
            f"inbox:{item.id}": item for item in self._unplanned_groups["inbox"]
        } | {
            f"next_actions:{item.id}": item
            for item in self._unplanned_groups["next_actions"]
        } | {
            f"project_tasks:{item.id}": item
            for item in self._unplanned_groups["project_tasks"]
        }
        self._refresh_supporting_panes()

    def action_add_to_top(self) -> None:
        """Add the selected candidate to Top 3 in planning mode."""
        if self._mode == "plan":
            option = self._selected_candidate()
        elif self._mode == "focus" and self._draft_focus == "wrap":
            option = self._selected_unplanned_item()
        else:
            return
        if option is None or option in self._top_items:
            return
        if len(self._top_items) >= 3:
            if self._mode == "focus":
                self._pending_top_replacement_item = option
                self.app.push_screen(
                    TopThreeReplacementDialog(self._top_items, option),
                    callback=self._apply_top_three_replacement_choice,
                )
                return
            self.notify("Top 3 is full. Remove or demote an item first.", timeout=2)
            return
        if self._mode == "focus":
            option = self._consume_selected_unplanned_item()
            if option is None:
                return
        self._top_items.append(option)
        if self._mode == "plan":
            self._draft_focus = "top"
            self._top_selected_index = len(self._top_items) - 1
        self._refresh_supporting_panes()

    def action_add_to_bonus(self) -> None:
        """Add the selected candidate to Bonus in planning mode."""
        if self._mode == "plan":
            option = self._selected_candidate()
        elif self._mode == "focus" and self._draft_focus == "wrap":
            option = self._consume_selected_unplanned_item()
        else:
            return
        if option is None or option in self._bonus_items:
            return
        self._bonus_items.append(option)
        if self._mode == "plan":
            self._draft_focus = "bonus"
            self._bonus_selected_index = len(self._bonus_items) - 1
        self._refresh_supporting_panes()

    def action_remove_selected_draft_item(self) -> None:
        """Remove the selected item from the active draft pane."""
        if self._mode == "focus" and self._draft_focus != "wrap":
            selected = self._selected_today_item()
            bucket_and_index = self._selected_today_bucket_and_index()
            if selected is None or bucket_and_index is None:
                return
            bucket, _index = bucket_and_index
            if bucket == "top":
                self._top_items = [item for item in self._top_items if item.id != selected.id]
            else:
                self._bonus_items = [item for item in self._bonus_items if item.id != selected.id]
            self._restore_to_unplanned(selected)
            self._refresh_supporting_panes()
            return
        if self._mode != "plan":
            return
        if self._draft_focus == "top":
            selected = self._selected_top_item()
            if selected is None:
                return
            self._top_items = [item for item in self._top_items if item.id != selected.id]
            self._top_selected_index = max(0, min(self._top_selected_index, len(self._top_items) - 1))
        elif self._draft_focus == "bonus":
            selected = self._selected_bonus_item()
            if selected is None:
                return
            self._bonus_items = [item for item in self._bonus_items if item.id != selected.id]
            self._bonus_selected_index = max(0, min(self._bonus_selected_index, len(self._bonus_items) - 1))
        else:
            return
        self._refresh_supporting_panes()

    def action_promote_bonus_item(self) -> None:
        """Promote the selected Bonus item into Top 3."""
        if self._mode == "plan":
            selected = self._selected_bonus_item()
            if selected is None or len(self._top_items) >= 3:
                return
            self._bonus_items = [item for item in self._bonus_items if item.id != selected.id]
            self._top_items.append(selected)
            self._draft_focus = "top"
            self._top_selected_index = len(self._top_items) - 1
            self._bonus_selected_index = max(0, min(self._bonus_selected_index, len(self._bonus_items) - 1))
            self._refresh_supporting_panes()
            return
        if self._mode != "focus":
            return
        bucket_and_index = self._selected_today_bucket_and_index()
        if bucket_and_index is None or bucket_and_index[0] != "bonus" or len(self._top_items) >= 3:
            return
        _bucket, index = bucket_and_index
        selected = self._bonus_items.pop(index)
        self._top_items.append(selected)
        self._refresh_supporting_panes()

    def action_demote_top_item(self) -> None:
        """Demote the selected Top 3 item into Bonus."""
        if self._mode == "plan":
            selected = self._selected_top_item()
            if selected is None:
                return
            self._top_items = [item for item in self._top_items if item.id != selected.id]
            self._bonus_items.append(selected)
            self._draft_focus = "bonus"
            self._bonus_selected_index = len(self._bonus_items) - 1
            self._top_selected_index = max(0, min(self._top_selected_index, len(self._top_items) - 1))
            self._refresh_supporting_panes()
            return
        if self._mode != "focus":
            return
        bucket_and_index = self._selected_today_bucket_and_index()
        if bucket_and_index is None or bucket_and_index[0] != "top":
            return
        _bucket, index = bucket_and_index
        selected = self._top_items.pop(index)
        self._bonus_items.append(selected)
        self._refresh_supporting_panes()

    def action_move_top_item_up(self) -> None:
        """Move the selected Top 3 item up."""
        if len(self._top_items) < 2:
            return
        if self._mode == "plan":
            self._sync_draft_index_from_primary_list()
            index = max(0, min(self._top_selected_index, len(self._top_items) - 1))
        elif self._mode == "focus":
            bucket_and_index = self._selected_today_bucket_and_index()
            if bucket_and_index is None or bucket_and_index[0] != "top":
                return
            index = bucket_and_index[1]
        else:
            return
        if index == 0:
            return
        self._top_items[index - 1], self._top_items[index] = (
            self._top_items[index],
            self._top_items[index - 1],
        )
        self._draft_focus = "top"
        self._top_selected_index = index - 1
        self._refresh_supporting_panes()

    def action_move_top_item_down(self) -> None:
        """Move the selected Top 3 item down."""
        if len(self._top_items) < 2:
            return
        if self._mode == "plan":
            self._sync_draft_index_from_primary_list()
            index = max(0, min(self._top_selected_index, len(self._top_items) - 1))
        elif self._mode == "focus":
            bucket_and_index = self._selected_today_bucket_and_index()
            if bucket_and_index is None or bucket_and_index[0] != "top":
                return
            index = bucket_and_index[1]
        else:
            return
        if index >= len(self._top_items) - 1:
            return
        self._top_items[index + 1], self._top_items[index] = (
            self._top_items[index],
            self._top_items[index + 1],
        )
        self._draft_focus = "top"
        self._top_selected_index = index + 1
        self._refresh_supporting_panes()

    def action_cursor_down(self) -> None:
        """Move selection down in the active pane."""
        if self._mode == "plan" and self._draft_focus == "top":
            if self._top_items:
                self._top_selected_index = min(self._top_selected_index + 1, len(self._top_items) - 1)
                self._refresh_supporting_panes()
            return
        if self._mode == "plan" and self._draft_focus == "bonus":
            if self._bonus_items:
                self._bonus_selected_index = min(self._bonus_selected_index + 1, len(self._bonus_items) - 1)
                self._refresh_supporting_panes()
            return
        options = self._current_list_widget()
        if options is not None:
            options.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move selection up in the active pane."""
        if self._mode == "plan" and self._draft_focus == "top":
            if self._top_items:
                self._top_selected_index = max(self._top_selected_index - 1, 0)
                self._refresh_supporting_panes()
            return
        if self._mode == "plan" and self._draft_focus == "bonus":
            if self._bonus_items:
                self._bonus_selected_index = max(self._bonus_selected_index - 1, 0)
                self._refresh_supporting_panes()
            return
        options = self._current_list_widget()
        if options is not None:
            options.action_cursor_up()

    def action_focus_list_panel(self) -> None:
        """Focus the primary list pane."""
        self._draft_focus = "candidates" if self._mode == "plan" else "today"
        options = self._current_list_widget()
        if options is not None:
            options.focus()
        self._refresh_supporting_panes()

    def action_focus_detail_panel(self) -> None:
        """Focus the detail-related editing pane."""
        self._draft_focus = "top" if self._mode == "plan" else "detail"
        widget = self._safe_query_one("#detail-pane-scroll", ScrollableContainer)
        if widget is not None:
            widget.focus()
        self._refresh_supporting_panes()

    def action_focus_wrap_panel(self) -> None:
        """Focus the wrap-related pane."""
        self._draft_focus = "bonus" if self._mode == "plan" else "wrap"
        widget = self._safe_query_one("#wrap-pane-scroll", ScrollableContainer)
        if widget is not None:
            widget.focus()
        self._refresh_supporting_panes()

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

    def action_new_task(self) -> None:
        """Open inline quick capture from the daily workspace."""
        self.app.push_screen(
            QuickCaptureDialog(origin_label="Daily workspace"),
            callback=self._apply_quick_capture_result,
        )

    async def _apply_quick_capture_result(
        self, result: QuickCaptureResult | None
    ) -> None:
        """Persist quick-capture result and refresh the planning workspace."""
        if not result or result.get("action") != "submit":
            return

        text = result.get("text", "").strip()
        if not text:
            self.notify("Enter task text to create a new inbox task.", severity="warning", timeout=2)
            return

        try:
            await asyncio.to_thread(self._engine.capture, text)
        except Exception as exc:  # pragma: no cover - runtime safety net
            self.notify(f"Failed to create task: {exc}", severity="error", timeout=3)
            return

        self.notify(f"Captured: {text[:40]}", timeout=2)
        await self._refresh_async()

    def action_complete_planned_item(self) -> None:
        """Complete the selected planned item and refresh."""
        if self._mode != "focus":
            return
        item = self._selected_today_item()
        if item is None:
            return
        self._engine.complete_item(item.id)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._refresh_async())
            return
        loop.create_task(self._refresh_async())

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

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Refresh detail text when the primary list highlight changes."""
        if event.option_list.id != "daily-list":
            return
        self._refresh_supporting_panes()

    def action_show_daily_wrap(self) -> None:
        """Render wrap summary for the current plan."""
        self._show_wrap_summary = True
        self._wrap_summary = self._engine.get_daily_wrap_summary(self._plan_date)
        self._engine.mark_daily_plan_wrapped(self._plan_date)
        wrap_text = self._render_wrap_summary(self._wrap_summary)
        self._set_text("#wrap-pane-title", "[3] Daily Wrap")
        self._set_text("#wrap-content", wrap_text)
        self._set_text("#daily-wrap", wrap_text)
        self._refresh_supporting_panes()

    def action_generate_wrap_insight(self) -> None:
        """Generate optional AI insight for the current daily wrap."""
        asyncio.create_task(self._generate_wrap_insight_async())

    async def _generate_wrap_insight_async(self) -> None:
        insight = await asyncio.to_thread(
            self._engine.generate_daily_wrap_insight, self._plan_date
        )
        if self.is_mounted:
            self._set_text("#daily-insight", self._render_wrap_insight(insight))
