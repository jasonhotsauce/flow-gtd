"""Action screen: next actions list (65%) + RAG Sidecar (35%)."""

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.core.rag import query as rag_query
from flow.tui.common.widgets.sidecar import RAGContextPanel


class ActionScreen(Screen):
    """Split: 65% next-actions list, 35% Sidecar (RAG on highlight)."""

    CSS_PATH = "action.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("escape", "app.pop_screen", "Back"),
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
        self._items: list = []
        self._rag_task: Optional[asyncio.Task] = None
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
                yield Static("🔗 Related Context", id="sidecar-title")
                yield RAGContextPanel(id="sidecar")
        with Container(id="action-help"):
            yield Static(
                "j/k: Navigate │ Enter: Details │ c: Complete │ Tab: Focus Sidecar │ Esc: Back",
                id="action-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize action list on mount."""
        self._refresh_list()
        sidecar = self.query_one("#sidecar", RAGContextPanel)
        sidecar.clear_results()

    def _refresh_list(self) -> None:
        """Refresh the action list from database."""
        self._items = self._engine.next_actions()
        opt_list = self.query_one("#action-list", OptionList)
        opt_list.clear_options()

        count_widget = self.query_one("#action-count", Static)
        count_widget.update(f"({len(self._items)} items)")

        if not self._items:
            opt_list.add_option(Option("  📭  No next actions available", id="-1"))
            return

        for i, item in enumerate(self._items):
            title = item.title[:60] + "..." if len(item.title) > 60 else item.title
            # Priority indicator
            priority = getattr(item, "priority", "medium")
            if priority == "high":
                indicator = "🔴"
            elif priority == "low":
                indicator = "🟢"
            else:
                indicator = "🟡"
            opt_list.add_option(Option(f"  {indicator}  {title}", id=str(i)))

    def _on_highlight(self, idx: int) -> None:
        """Handle item highlight - trigger debounced RAG query."""
        if idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_rag(item.title))

    async def _debounced_rag(self, task_title: str) -> None:
        """Wait briefly before triggering RAG to avoid excessive queries."""
        await asyncio.sleep(0.3)
        await self._run_rag(task_title)

    async def _run_rag(self, task_title: str) -> None:
        """Run RAG query and update sidecar."""
        if self._rag_task and not self._rag_task.done():
            self._rag_task.cancel()

        sidecar = self.query_one("#sidecar", RAGContextPanel)
        sidecar.show_loading()

        self._rag_task = asyncio.create_task(
            asyncio.to_thread(rag_query, task_title, 3)
        )
        try:
            results = await self._rag_task
            sidecar.show_results(results)
        except asyncio.CancelledError:
            pass
        except Exception:
            sidecar.show_error("Failed to load context")

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
            self._refresh_list()

    def action_focus_sidecar(self) -> None:
        """Focus the sidecar panel."""
        sidecar = self.query_one("#sidecar", RAGContextPanel)
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
