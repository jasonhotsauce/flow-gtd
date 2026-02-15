"""Inbox screen: capture triage and list."""

import asyncio
from datetime import datetime

from rich.text import Text

from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.models import Item
from flow.tui.common.widgets.defer_dialog import DeferDialog
from flow.tui.common.widgets.process_task_dialog import ProcessTaskDialog
from flow.tui.common.widgets.project_picker_dialog import ProjectPickerDialog


class InboxScreen(Screen):
    """Screen showing inbox items. Default landing for TUI."""

    CSS_PATH = "inbox.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "open_process_menu", "Process"),
        ("d", "delete_item", "Delete"),
        ("f", "defer_item", "Defer"),
        ("p", "go_process", "Process"),
        ("g", "go_projects", "Projects"),
        Binding("a", "go_action", "Actions", show=False),
        Binding("r", "go_review", "Review", show=False),
        Binding("P", "go_projects", "Projects", show=False),
        ("?", "show_help", "Help"),
    ]

    def __init__(self, startup_context: dict[str, object] | None = None) -> None:
        super().__init__()
        self._engine = Engine()
        self._items: list[Item] = []
        self._startup_context = startup_context

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="inbox-header"):
            yield Static("📥 Inbox", id="inbox-title")
            yield Static("", id="inbox-count")
        with Container(id="inbox-stats"):
            yield Static("", id="inbox-stats-content")
        with Horizontal(id="inbox-content"):
            with Vertical(id="inbox-left"):
                with Container(id="inbox-list-container"):
                    yield OptionList(id="inbox-list")
            with Vertical(id="inbox-right"):
                yield Static("📄 Task", id="inbox-detail-title")
                with ScrollableContainer(id="inbox-detail-scroll"):
                    yield Static("", id="inbox-detail-body")
                yield Static("", id="inbox-detail-tags")
        with Vertical(id="inbox-empty"):
            yield Static("📭", id="inbox-empty-icon")
            yield Static("Your inbox is empty!", id="inbox-empty-text")
            yield Static(
                "Use 'flow c <text>' to capture new items", id="inbox-empty-hint"
            )
        with Container(id="inbox-help"):
            yield Static(
                "j/k: Navigate │ Enter: Process Menu │ d: Delete │ f: Defer │ p: Process │ g: Projects │ ?: Help",
                id="inbox-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load inbox items on mount."""
        asyncio.create_task(self._refresh_items_async())

    def _refresh_list(self) -> None:
        """Render inbox list from current in-memory items."""
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.clear_options()

        empty_container = self.query_one("#inbox-empty", Vertical)
        content_container = self.query_one("#inbox-content", Horizontal)
        count_widget = self.query_one("#inbox-count", Static)
        stats_widget = self.query_one("#inbox-stats-content", Static)

        if not self._items:
            empty_container.display = True
            content_container.display = False
            count_widget.update("")
            stats_widget.update("")
            self._update_detail_panel(None)
        else:
            empty_container.display = False
            content_container.display = True
            count_widget.update(f"({len(self._items)} items)")

            # Calculate stats
            today_count = sum(1 for it in self._items if self._is_today(it))
            stats_widget.update(
                f"📊 Total: {len(self._items)} │ 🆕 Today: {today_count}"
            )

            # List: short one-line preview; full text in detail panel
            for i, item in enumerate(self._items):
                preview = item.title.split("\n")[0].strip()
                if len(preview) > 48:
                    preview = preview[:48] + "…"
                bullet = "●" if self._is_today(item) else "○"
                opt_list.add_option(Option(f" {bullet}  {preview}", id=str(i)))

            startup_index = self._find_startup_highlight_index()
            if startup_index is not None:
                opt_list.highlighted = startup_index
                self._update_detail_panel(self._items[startup_index])
            else:
                # Show first item's full text and tags in detail panel
                try:
                    opt_list.action_first()
                    idx = opt_list.highlighted
                    if idx is not None and 0 <= idx < len(self._items):
                        self._update_detail_panel(self._items[idx])
                except Exception:
                    self._update_detail_panel(self._items[0] if self._items else None)
            try:
                opt_list.focus()
            except (ValueError, KeyError):
                pass

        self._consume_startup_context_once()

    async def _refresh_items_async(self) -> None:
        """Reload inbox rows in background, then render."""
        self._items = await asyncio.to_thread(self._engine.list_inbox)
        if self.is_mounted:
            self._refresh_list()

    def _is_today(self, item: Item) -> bool:
        """Check if item was created today."""
        from datetime import date

        if hasattr(item, "created_at") and item.created_at:
            try:
                return item.created_at.date() == date.today()
            except (AttributeError, TypeError):
                pass
        return False

    def _update_detail_panel(self, item: Item | None) -> None:
        """Update the right-hand detail panel with full task text and tags."""
        body = self.query_one("#inbox-detail-body", Static)
        tags_widget = self.query_one("#inbox-detail-tags", Static)
        if item is None:
            body.update("Select a task to view full text and tags.")
            tags_widget.update("")
        else:
            body.update(item.title)
            if item.context_tags:
                tag_text = Text()
                tag_text.append("Tags: ", style="dim")
                tag_text.append(", ".join(item.context_tags), style="bold #a78bfa")
                tags_widget.update(tag_text)
            else:
                tags_widget.update("")

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update detail panel when selection changes."""
        try:
            idx = int(event.option.id)
        except (ValueError, TypeError):
            idx = -1
        if 0 <= idx < len(self._items):
            self._update_detail_panel(self._items[idx])

    def action_cursor_down(self) -> None:
        """Move cursor down in list."""
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in list."""
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.action_cursor_up()

    def _selected_item(self) -> Item | None:
        """Return currently highlighted inbox item."""
        if not self._items:
            return None
        opt_list = self.query_one("#inbox-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            return self._items[idx]
        return None

    def _find_startup_highlight_index(self) -> int | None:
        """Resolve one-time startup highlight target index from startup context."""
        if not self._startup_context:
            return None
        highlighted_item_id = self._startup_context.get("highlighted_item_id")
        if not isinstance(highlighted_item_id, str) or not highlighted_item_id:
            return None
        for idx, item in enumerate(self._items):
            if item.id == highlighted_item_id:
                return idx
        return None

    def _consume_startup_context_once(self) -> None:
        """Apply one-time first-value hint and clear startup context."""
        if not self._startup_context:
            return

        if self._startup_context.get("show_first_value_hint") is True:
            self.notify(
                "Captured your first inbox item. Start by clarifying the next action."
            )
        self._startup_context = None

    def action_process_item(self) -> None:
        """Back-compat action alias for process menu."""
        self.action_open_process_menu()

    def action_open_process_menu(self) -> None:
        """Open process menu for selected inbox item."""
        item = self._selected_item()
        if item is None:
            return
        self.app.push_screen(
            ProcessTaskDialog(),
            callback=lambda result: self._apply_process_result(item.id, result),
        )

    def _apply_process_result(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Apply selected process action for an inbox item."""
        if result and result.get("action") == "add_to_project":
            self._open_project_picker(item_id)
            return
        try:
            asyncio.get_running_loop().create_task(
                self._apply_process_result_async(item_id, result)
            )
        except RuntimeError:
            # Fallback for unit tests and non-async contexts.
            if not result:
                return
            action = result.get("action")
            if action == "do_now":
                item = self._engine.get_item(item_id)
                if item:
                    self.notify(f"Processing: {item.title[:40]}...", timeout=2)
            elif action == "delete":
                item = self._engine.get_item(item_id)
                if item:
                    self._engine.archive_item(item.id)
                    self.notify(
                        f"🗑️ Archived: {item.title[:30]}...",
                        severity="warning",
                        timeout=2,
                    )
                    self._refresh_list()

    async def _apply_process_result_async(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Apply selected process action for an inbox item."""
        if not result:
            return
        action = result.get("action")
        if action == "do_now":
            item = await asyncio.to_thread(self._engine.get_item, item_id)
            if item:
                self.notify(f"Processing: {item.title[:40]}...", timeout=2)
            return
        if action == "defer":
            self.app.push_screen(
                DeferDialog(),
                callback=lambda defer_result: self._apply_defer_result(
                    item_id, defer_result
                ),
            )
            return
        if action == "delete":
            item = await asyncio.to_thread(self._engine.get_item, item_id)
            if item is None:
                self.notify(
                    "Item no longer exists. Refreshing…",
                    severity="warning",
                    timeout=2,
                )
                asyncio.create_task(self._refresh_items_async())
                return
            await asyncio.to_thread(self._engine.archive_item, item.id)
            self.notify(
                f"🗑️ Archived: {item.title[:30]}...", severity="warning", timeout=2
            )
            asyncio.create_task(self._refresh_items_async())
            return
        if action == "add_to_project":
            self._open_project_picker(item_id)

    def _open_project_picker(self, item_id: str) -> None:
        """Open project picker for assigning the selected item."""
        asyncio.create_task(self._open_project_picker_async(item_id))

    async def _open_project_picker_async(self, item_id: str) -> None:
        """Open project picker with DB reads off the UI thread."""
        item = await asyncio.to_thread(self._engine.get_item, item_id)
        if item is None:
            self.notify(
                "Item no longer exists. Refreshing…", severity="warning", timeout=2
            )
            self._refresh_list()
            return

        projects = await asyncio.to_thread(self._engine.list_projects)
        if not projects:
            self.notify(
                "No active projects yet. Create one in Process Stage 2.",
                severity="warning",
                timeout=3,
            )
            return

        self.app.push_screen(
            ProjectPickerDialog(projects),
            callback=lambda picker_result: self._apply_project_assignment(
                item_id, picker_result
            ),
        )

    def _apply_project_assignment(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Assign selected item to selected project."""
        asyncio.create_task(self._apply_project_assignment_async(item_id, result))

    async def _apply_project_assignment_async(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Assign selected item to selected project off the UI thread."""
        if not result:
            return
        project_id = result.get("project_id")
        if not project_id:
            self.notify("No project selected", severity="warning", timeout=2)
            return

        try:
            await asyncio.to_thread(
                self._engine.assign_item_to_project, item_id, project_id
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=3)
            self._refresh_list()
            return

        project = await asyncio.to_thread(self._engine.get_item, project_id)
        project_name = project.title if project else "project"
        self.notify(f"📁 Added to project: {project_name}", timeout=2)
        await self._refresh_items_async()

    def action_delete_item(self) -> None:
        """Delete the selected item."""
        if not self._items:
            return
        opt_list = self.query_one("#inbox-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            item = self._items[idx]
            asyncio.create_task(self._archive_item_async(item.id, item.title))

    async def _archive_item_async(self, item_id: str, title: str) -> None:
        await asyncio.to_thread(self._engine.archive_item, item_id)
        if self.is_mounted:
            self.notify(f"🗑️ Archived: {title[:30]}...", severity="warning", timeout=2)
            await self._refresh_items_async()

    def action_defer_item(self) -> None:
        """Defer the selected inbox item using the shared defer chooser."""
        if not self._items:
            return

        opt_list = self.query_one("#inbox-list", OptionList)
        idx = opt_list.highlighted
        if idx is None or idx < 0 or idx >= len(self._items):
            return

        item = self._items[idx]
        self.app.push_screen(
            DeferDialog(),
            callback=lambda result: self._apply_defer_result(item.id, result),
        )

    def _apply_defer_result(self, item_id: str, result: dict[str, str] | None) -> None:
        """Apply defer selection and refresh inbox list."""
        asyncio.create_task(self._apply_defer_result_async(item_id, result))

    async def _apply_defer_result_async(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Apply defer selection and refresh inbox list."""
        if not result:
            return

        item = await asyncio.to_thread(self._engine.get_item, item_id)
        if not item:
            self.notify(
                "Item no longer exists. Refreshing…", severity="warning", timeout=2
            )
            await self._refresh_items_async()
            return

        mode = result.get("mode")
        if mode == "waiting":
            await asyncio.to_thread(self._engine.defer_item, item.id, "waiting")
            self.notify("⏳ Deferred to Waiting For", timeout=2)
        elif mode == "someday":
            await asyncio.to_thread(self._engine.defer_item, item.id, "someday")
            self.notify("🌱 Moved to Someday/Maybe", timeout=2)
        elif mode == "until":
            raw = result.get("defer_until", "")
            parsed: datetime | None = None
            if raw:
                try:
                    parsed = datetime.fromisoformat(raw)
                except ValueError:
                    parsed = None
            if parsed is None:
                self.notify("Unable to parse defer date", severity="error", timeout=3)
                return
            await asyncio.to_thread(self._engine.defer_item, item.id, "until", parsed)
            self.notify(
                f"📅 Deferred until {parsed.strftime('%Y-%m-%d %H:%M')}", timeout=2
            )
        else:
            return

        await self._refresh_items_async()

    def action_go_process(self) -> None:
        """Navigate to process screen."""
        from flow.tui.screens.process.process import ProcessScreen

        self.app.push_screen(ProcessScreen())

    def action_go_action(self) -> None:
        """Navigate to action screen."""
        from flow.tui.screens.action.action import ActionScreen

        self.app.push_screen(ActionScreen())

    def action_go_review(self) -> None:
        """Navigate to review screen."""
        from flow.tui.screens.review.review import ReviewScreen

        self.app.push_screen(ReviewScreen())

    def action_go_projects(self) -> None:
        """Navigate to projects screen."""
        from flow.tui.screens.projects.projects import ProjectsScreen

        self.app.push_screen(ProjectsScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "j/k: Navigate │ Enter: Process Menu │ d: Delete │ f: Defer │ p: Process │ g: Projects\n"
            "a: Actions │ r: Review │ q: Quit",
            title="Help",
            timeout=5,
        )
