"""Project detail screen: list and work next actions for one project (GTD proceed)."""

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


class ProjectDetailScreen(Screen):
    """Screen to work through a project's next actions. Complete or defer; Esc back to list."""

    CSS_PATH = "projects.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("escape", "pop_screen", "Back"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("enter", "select_action", "Select", show=False),
        ("c", "complete_action", "Complete"),
        ("f", "defer_action", "Defer"),
        ("?", "show_help", "Help"),
    ]

    def __init__(self, project: Item) -> None:
        super().__init__()
        self._engine = Engine()
        self._project = project
        self._actions: list[Item] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="detail-header"):
            yield Static("", id="detail-title")
            yield Static("", id="detail-count")
        with Horizontal(id="detail-content"):
            with Vertical(id="detail-left"):
                with Container(id="detail-list-container"):
                    yield OptionList(id="detail-list")
            with Vertical(id="detail-right"):
                yield Static("Task", id="detail-body-title")
                with ScrollableContainer(id="detail-body-scroll"):
                    yield Static("", id="detail-body")
                yield Static("", id="detail-tags")
        with Vertical(id="detail-loading"):
            yield Static("Loading actions…", id="detail-loading-text")
        with Vertical(id="detail-empty"):
            yield Static(
                "No next actions. Define one or put project on hold.",
                id="detail-empty-text",
            )
        with Container(id="detail-help"):
            yield Static(
                "j/k: Navigate │ c: Complete │ f: Defer │ Esc: Back │ ?: Help",
                id="detail-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Set title and load actions in background."""
        self.query_one("#detail-title", Static).update(f"📁 {self._project.title}")
        self._show_loading()
        asyncio.create_task(self._refresh_list_async())

    def _show_loading(self) -> None:
        """Show loading state, hide content and empty."""
        self.query_one("#detail-loading", Vertical).display = True
        self.query_one("#detail-content", Horizontal).display = False
        self.query_one("#detail-empty", Vertical).display = False
        self.query_one("#detail-count", Static).update("")

    async def _refresh_list_async(self) -> None:
        """Load project actions off the main thread, then apply to UI."""
        try:
            actions = await asyncio.to_thread(
                self._engine.next_actions, self._project.id
            )
            if not self.is_mounted:
                return
            self._apply_list(actions)
        except Exception:
            if self.is_mounted:
                self._actions = []
                self._apply_list([])
                self.notify("Failed to load actions", severity="error", timeout=3)

    def _apply_list(self, actions: list[Item]) -> None:
        """Render action list from in-memory data (no DB calls)."""
        had_actions = bool(self._actions)
        self._actions = actions
        opt_list = self.query_one("#detail-list", OptionList)
        opt_list.clear_options()

        self.query_one("#detail-loading", Vertical).display = False
        empty = self.query_one("#detail-empty", Vertical)
        content = self.query_one("#detail-content", Horizontal)
        count_widget = self.query_one("#detail-count", Static)

        if not self._actions:
            empty.display = True
            content.display = False
            count_widget.update("")
            self._update_detail_panel(None)
            if had_actions:
                self.notify(
                    "Project has no next actions. Define one or put project on hold.",
                    title="GTD",
                    timeout=4,
                )
        else:
            empty.display = False
            content.display = True
            count_widget.update(f"({len(self._actions)} actions)")

            for i, item in enumerate(self._actions):
                preview = item.title.split("\n")[0].strip()
                if len(preview) > 48:
                    preview = preview[:48] + "…"
                opt_list.add_option(Option(f"  •  {preview}", id=str(i)))

            try:
                opt_list.action_first()
                idx = opt_list.highlighted
                if idx is not None and 0 <= idx < len(self._actions):
                    self._update_detail_panel(self._actions[idx])
            except Exception:
                self._update_detail_panel(self._actions[0] if self._actions else None)
            try:
                opt_list.focus()
            except (ValueError, KeyError):
                pass

    def _update_detail_panel(self, item: Item | None) -> None:
        """Update right panel with full task text and tags."""
        body = self.query_one("#detail-body", Static)
        tags_widget = self.query_one("#detail-tags", Static)
        if item is None:
            body.update("Select an action to view full text and tags.")
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
        """Update detail when selection changes."""
        try:
            idx = int(event.option.id)
        except (ValueError, TypeError):
            idx = -1
        if 0 <= idx < len(self._actions):
            self._update_detail_panel(self._actions[idx])

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        self.query_one("#detail-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        self.query_one("#detail-list", OptionList).action_cursor_up()

    def action_select_action(self) -> None:
        """Select current action (no-op; detail already shown)."""
        if self._actions:
            opt_list = self.query_one("#detail-list", OptionList)
            idx = opt_list.highlighted
            if idx is not None and 0 <= idx < len(self._actions):
                self.notify(
                    f"Selected: {self._actions[idx].title[:40]}…",
                    timeout=2,
                )

    def action_complete_action(self) -> None:
        """Mark selected action done."""
        if not self._actions:
            return
        opt_list = self.query_one("#detail-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._actions):
            item = self._actions[idx]
            self._engine.complete_item(item.id)
            self.notify(
                f"✅ Completed: {item.title[:30]}…",
                severity="information",
                timeout=2,
            )
            asyncio.create_task(self._refresh_list_async())

    def action_defer_action(self) -> None:
        """Defer selected action using defer chooser."""
        if not self._actions:
            return
        opt_list = self.query_one("#detail-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._actions):
            item = self._actions[idx]
            self.app.push_screen(
                DeferDialog(),
                callback=lambda result: self._apply_defer_result(item.id, result),
            )

    def _apply_defer_result(self, item_id: str, result: dict[str, str] | None) -> None:
        """Apply defer selection and refresh list."""
        if not result:
            return

        item = self._engine.get_item(item_id)
        if not item:
            self.notify(
                "Item no longer exists. Refreshing…", severity="warning", timeout=2
            )
            asyncio.create_task(self._refresh_list_async())
            return

        mode = result.get("mode")
        if mode == "waiting":
            self._engine.defer_item(item.id, mode="waiting")
            self.notify(
                f"⏸ Waiting For: {item.title[:30]}…",
                severity="information",
                timeout=2,
            )
        elif mode == "someday":
            self._engine.defer_item(item.id, mode="someday")
            self.notify(
                f"🌱 Someday/Maybe: {item.title[:30]}…",
                severity="information",
                timeout=2,
            )
        elif mode == "until":
            raw = result.get("defer_until", "")
            parsed = None
            if raw:
                try:
                    parsed = datetime.fromisoformat(raw)
                except ValueError:
                    parsed = None
            if parsed is None:
                self.notify("Unable to parse defer date", severity="error", timeout=3)
                return

            self._engine.defer_item(item.id, mode="until", defer_until=parsed)
            self.notify(
                f"📅 Deferred until {parsed.strftime('%Y-%m-%d %H:%M')}",
                severity="information",
                timeout=2,
            )
        else:
            return

        asyncio.create_task(self._refresh_list_async())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "📖 Project detail (GTD proceed)\n"
            "c: Complete │ f: Defer\n"
            "Esc: Back to project list",
            title="Help",
            timeout=5,
        )

    def action_pop_screen(self) -> None:
        """Pop back to project list."""
        self.app.pop_screen()
