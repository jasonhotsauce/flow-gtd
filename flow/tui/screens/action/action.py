"""Action screen: next actions list (65%) + Resource Sidecar (35%)."""

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.models import Item
from flow.tui.common.widgets.sidecar import ResourceContextPanel


class ActionScreen(Screen):
    """Split: 65% next-actions list, 35% Sidecar (resources by tags)."""

    CSS_PATH = "action.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("escape", "pop_screen", "Back"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "select_action", "Select"),
        ("c", "complete_action", "Complete"),
        ("tab", "focus_sidecar", "Focus Sidecar"),
        ("i", "go_inbox", "Inbox"),
        ("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._items: list[Item] = []
        self._debounce_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="action-header"):
            yield Static("⚡ Next Actions", id="action-title")
            yield Static("", id="action-count")
        with Horizontal(id="action-content"):
            with Vertical(id="action-left"):
                yield Static("📋 Tasks", id="action-list-title")
                yield OptionList(id="action-list")
            with Vertical(id="action-right"):
                yield Static("🔗 Related Resources", id="sidecar-title")
                yield ResourceContextPanel(id="sidecar")
        with Container(id="action-help"):
            yield Static(
                "j/k: Navigate │ Enter: Details │ c: Complete │ Tab: Focus Sidecar │ Esc: Back",
                id="action-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize action list on mount (load in background to avoid blocking)."""
        sidecar = self.query_one("#sidecar", ResourceContextPanel)
        sidecar.clear_resources()
        count_widget = self.query_one("#action-count", Static)
        count_widget.update("(loading…)")
        asyncio.create_task(self._refresh_list_async())
        try:
            self.query_one("#action-list", OptionList).focus()
        except (ValueError, KeyError):
            pass

    async def _refresh_list_async(self) -> None:
        """Load next actions in a background thread and update UI when ready."""
        try:
            items = await asyncio.to_thread(self._engine.next_actions)
            if not self.is_mounted:
                return
            self._items = items
            self._apply_items_to_ui()
        except Exception:
            if self.is_mounted:
                self._items = []
                self._apply_items_to_ui()
                self.notify("Failed to load actions", severity="error", timeout=3)

    def _apply_items_to_ui(self) -> None:
        """Update OptionList and count from current self._items (no DB call)."""
        opt_list = self.query_one("#action-list", OptionList)
        opt_list.clear_options()

        count_widget = self.query_one("#action-count", Static)
        count_widget.update(f"({len(self._items)} items)")

        if not self._items:
            opt_list.add_option(Option("  📭  No next actions available", id="-1"))
            return

        for i, item in enumerate(self._items):
            title = item.title
            # Priority from meta_payload: 1 or "high" -> high, 3 or "low" -> low
            raw = item.meta_payload.get("priority")
            if raw == 1 or raw == "high":
                priority = "high"
            elif raw == 3 or raw == "low":
                priority = "low"
            else:
                priority = "medium"
            if priority == "high":
                indicator = "🔴"
            elif priority == "low":
                indicator = "🟢"
            else:
                indicator = "🟡"
            opt_list.add_option(Option(f"  {indicator}  {title}", id=str(i)))

    def _on_highlight(self, idx: int) -> None:
        """Handle item highlight - show matching resources."""
        if idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._show_resources(item))

    async def _show_resources(self, item: Item) -> None:
        """Show resources matching the task's tags.

        Uses a small debounce to avoid flickering on rapid navigation.
        """
        await asyncio.sleep(0.1)  # Small debounce
        sidecar = self.query_one("#sidecar", ResourceContextPanel)

        try:
            # Get resources matching the task's tags
            resources = self._engine.get_resources_by_tags(item.context_tags)
            sidecar.show_resources(resources, task_tags=item.context_tags)
        except (IOError, ValueError, RuntimeError):
            sidecar.show_error("Failed to load resources")

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight event."""
        try:
            idx = int(event.option.id) if event.option.id != "-1" else -1
        except (ValueError, TypeError):
            idx = -1
        if idx >= 0:
            self._on_highlight(idx)

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        opt_list = self.query_one("#action-list", OptionList)
        opt_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        opt_list = self.query_one("#action-list", OptionList)
        opt_list.action_cursor_up()

    def action_select_action(self) -> None:
        """Select the current action."""
        if not self._items:
            return
        opt_list = self.query_one("#action-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            item = self._items[idx]
            self.notify(f"📌 Selected: {item.title[:40]}...", timeout=2)

    def action_complete_action(self) -> None:
        """Mark the current action as complete."""
        if not self._items:
            return
        opt_list = self.query_one("#action-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            item = self._items[idx]
            self._engine.complete_item(item.id)
            self.notify(
                f"✅ Completed: {item.title[:30]}...",
                severity="information",
                timeout=2,
            )
            asyncio.create_task(self._refresh_list_async())

    def action_focus_sidecar(self) -> None:
        """Focus the sidecar panel."""
        sidecar = self.query_one("#sidecar", ResourceContextPanel)
        sidecar.focus()

    def action_go_inbox(self) -> None:
        """Navigate to inbox."""
        from flow.tui.screens.inbox.inbox import InboxScreen

        self.app.push_screen(InboxScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "📖 Keyboard shortcuts:\n"
            "j/k: Navigate │ Enter: Select\n"
            "c: Complete task │ Tab: Sidecar\n"
            "i: Inbox │ Esc: Back │ q: Quit",
            title="Help",
            timeout=5,
        )

    def action_pop_screen(self) -> None:
        """Pop current screen; if it's the only screen (e.g. launched via `flow next`), quit instead."""
        if len(self.app.screen_stack) <= 2:
            self.app.exit()
        else:
            self.app.pop_screen()
