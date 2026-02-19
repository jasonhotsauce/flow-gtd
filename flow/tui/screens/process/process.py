"""Process Funnel: 4-stage wizard (Dedup, Cluster, 2-Min, Coach)."""

import asyncio
from datetime import datetime

from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.core.coach import coach_task
from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.keybindings import with_global_bindings
from flow.tui.common.widgets.defer_dialog import DeferDialog


class ProcessScreen(FlowScreen):
    """TUI Wizard for Process Funnel: Dedup -> Cluster -> 2-Min -> Coach."""

    CSS_PATH = "process.tcss"

    BINDINGS = with_global_bindings(
        Binding("1", "stage1", "Dedup", show=False),
        Binding("2", "stage2", "Cluster", show=False),
        Binding("3", "stage3", "2-Min", show=False),
        Binding("4", "stage4", "Coach", show=False),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("m", "merge", "Merge", show=False),
        Binding("b", "keep_both", "Keep Both", show=False),
        Binding("enter", "primary", "Primary Action", show=False),
        Binding("d", "do_now", "Do Now", show=False),
        Binding("f", "defer", "Defer", show=False),
        Binding("x", "delete", "Delete", show=False),
        Binding("c", "create_project", "Create", show=False),
        Binding("a", "accept", "Accept", show=False),
        Binding("n", "skip", "Skip", show=False),
    )

    STAGE_INFO = {
        1: ("🔀 Deduplication", "Find and merge duplicate items"),
        2: ("📁 Clustering", "Group related items into projects"),
        3: ("⚡ 2-Minute Drill", "Quick wins: do now or defer"),
        4: ("🧠 Coach", "AI helps clarify vague tasks"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._stage = 1
        self._dedup_pair: tuple | None = None
        self._cluster_suggestions: list = []
        self._cluster_selected = 0
        self._coach_suggestion: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="process-header"):
            yield Static("🔄 Process Funnel", id="process-main-title")
        with Horizontal(id="process-progress"):
            yield Static("1️⃣ Dedup", id="step-1", classes="step -active")
            yield Static("2️⃣ Cluster", id="step-2", classes="step")
            yield Static("3️⃣ 2-Min", id="step-3", classes="step")
            yield Static("4️⃣ Coach", id="step-4", classes="step")
        with Container(id="process-stage"):
            yield Static("", id="process-stage-title")
            yield Static("", id="process-stage-desc")
        with Container(id="process-content"):
            # Dedup view
            with Horizontal(id="dedup-container"):
                with Vertical(id="dedup-left"):
                    yield Static("Item A", classes="dedup-label")
                    yield Static("", id="dedup-a-title", classes="dedup-title")
                with Vertical(id="dedup-right"):
                    yield Static("Item B", classes="dedup-label")
                    yield Static("", id="dedup-b-title", classes="dedup-title")
            # Cluster view
            yield OptionList(id="cluster-list")
            # 2-Min view
            with Vertical(id="twomin-card"):
                yield Static("⏱️", id="twomin-icon")
                yield Static("", id="twomin-title")
                yield Static("", id="twomin-hint")
            # Coach view
            with Vertical(id="coach-panel"):
                with Container(id="coach-task"):
                    yield Static("Current Task:", id="coach-task-label")
                    yield Static("", id="coach-task-title")
                with Container(id="coach-suggestion"):
                    yield Static("💡 AI Suggestion:", id="coach-suggestion-label")
                    yield Static("", id="coach-suggestion-text")
            # Empty/Complete state
            with Vertical(id="complete-state", classes="complete-state"):
                yield Static("✅", id="complete-icon", classes="complete-icon")
                yield Static("", id="complete-text", classes="complete-text")
        with Container(id="process-help"):
            yield Static("", id="process-cta-text")
            yield Static("", id="process-help-text")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize process screen."""
        asyncio.create_task(self._init_async())

    async def _init_async(self) -> None:
        await asyncio.to_thread(self._engine.process_start)
        if self.is_mounted:
            self._go_stage(1)

    def _update_progress(self) -> None:
        """Update progress bar visual state."""
        for i in range(1, 5):
            step = self.query_one(f"#step-{i}", Static)
            step.remove_class("-active", "-complete")
            if i < self._stage:
                step.add_class("-complete")
            elif i == self._stage:
                step.add_class("-active")

    def _hide_all_views(self) -> None:
        """Hide all content views."""
        self.query_one("#dedup-container", Horizontal).display = False
        self.query_one("#cluster-list", OptionList).display = False
        self.query_one("#twomin-card", Vertical).display = False
        self.query_one("#coach-panel", Vertical).display = False
        self.query_one("#complete-state", Vertical).display = False

    def _go_stage(self, stage: int) -> None:
        """Navigate to a specific stage."""
        self._stage = stage
        self._update_progress()
        self._hide_all_views()

        title, desc = self.STAGE_INFO.get(stage, ("", ""))
        self.query_one("#process-stage-title", Static).update(title)
        self.query_one("#process-stage-desc", Static).update(desc)
        self._update_stage_guidance(stage)

        if stage == 1:
            self._render_dedup()
        elif stage == 2:
            self._render_cluster()
        elif stage == 3:
            self._render_twomin()
        elif stage == 4:
            self._render_coach()

    def _render_dedup(self) -> None:
        """Render deduplication stage."""
        pair = self._engine.get_dedup_pair()
        self._dedup_pair = pair

        if not pair:
            self.query_one("#complete-state", Vertical).display = True
            self.query_one("#complete-text", Static).update(
                "No duplicates found! Press 2 for Clustering."
            )
            self._update_stage_guidance(
                1,
                primary="Primary: Enter to Continue to Cluster",
                controls="2: Next Stage │ 1-4: Jump to Stage │ Esc: Back",
                next_step="Next: Start grouping related tasks into projects.",
            )
            return

        self.query_one("#dedup-container", Horizontal).display = True
        a, b = pair
        self.query_one("#dedup-a-title", Static).update(a.title[:80])
        self.query_one("#dedup-b-title", Static).update(b.title[:80])
        self._update_stage_guidance(
            1, controls="m: Merge (keep A) │ b: Keep Both │ 2: Skip to Cluster"
        )

    def _render_cluster(self) -> None:
        """Render clustering stage."""
        self._cluster_suggestions = []
        self.query_one("#cluster-list", OptionList).display = True
        opt_list = self.query_one("#cluster-list", OptionList)
        opt_list.clear_options()
        opt_list.add_option(Option("  ⏳  Loading clusters…", id="loading"))
        self._update_stage_guidance(
            2,
            primary="Primary: Enter to Create Project",
            controls="Loading cluster suggestions…",
            next_step="Next: Promote one cluster, then move to 2-Min.",
        )
        asyncio.create_task(self._render_cluster_async())

    async def _render_cluster_async(self) -> None:
        suggestions = await asyncio.to_thread(self._engine.get_cluster_suggestions)
        if not self.is_mounted or self._stage != 2:
            return
        self._cluster_suggestions = suggestions
        opt_list = self.query_one("#cluster-list", OptionList)
        opt_list.clear_options()
        if not self._cluster_suggestions:
            self.query_one("#cluster-list", OptionList).display = False
            self.query_one("#complete-state", Vertical).display = True
            self.query_one("#complete-text", Static).update(
                "No clusters found. Press 3 for 2-Min Drill."
            )
            self._update_stage_guidance(
                2,
                primary="Primary: Enter to Continue to 2-Min",
                controls="3: Next Stage │ 1-4: Jump to Stage │ Esc: Back",
                next_step="Next: Process quick wins in 2-Min Drill.",
            )
            return
        for i, (name, ids) in enumerate(self._cluster_suggestions):
            opt_list.add_option(
                Option(f"  📁  {name} ({len(ids)} items)", id=f"cluster-{i}")
            )
        self._update_stage_guidance(
            2, controls="j/k: Navigate │ c: Create Project │ n: Skip │ 3: Next Stage"
        )

    def _render_twomin(self) -> None:
        """Render 2-minute drill stage."""
        item = self._engine.get_2min_current()

        if not item:
            self.query_one("#complete-state", Vertical).display = True
            self.query_one("#complete-text", Static).update(
                "2-Min Drill complete! Press 4 for Coach."
            )
            self._update_stage_guidance(
                3,
                primary="Primary: Enter to Continue to Coach",
                controls="4: Next Stage │ 1-4: Jump to Stage │ Esc: Back",
                next_step="Next: Use Coach for the remaining unclear tasks.",
            )
            return

        self.query_one("#twomin-card", Vertical).display = True
        self.query_one("#twomin-title", Static).update(item.title)
        self.query_one("#twomin-hint", Static).update("Can you do this in 2 minutes?")
        self._update_stage_guidance(
            3, controls="d: Do Now │ f: Defer │ x: Delete │ 4: Skip to Coach"
        )

    def _render_coach(self) -> None:
        """Render coach stage."""
        item = self._engine.get_coach_current()

        if not item:
            self.query_one("#complete-state", Vertical).display = True
            self.query_one("#complete-icon", Static).update("🎉")
            self.query_one("#complete-text", Static).update(
                "Process complete! You're all set."
            )
            self._update_stage_guidance(
                4,
                primary="Primary: Enter to Exit Process",
                controls="Press Esc or q to exit │ 1-4: Review stages",
                next_step="Next: Return to Inbox and keep capture moving.",
            )
            return

        self.query_one("#coach-panel", Vertical).display = True
        self.query_one("#coach-task-title", Static).update(item.title)
        self.query_one("#coach-suggestion-text", Static).update("Generating suggestion…")
        self._update_stage_guidance(
            4, controls="a: Accept suggestion │ n: Skip │ Esc: Back"
        )
        asyncio.create_task(self._load_coach_suggestion_async(item.title))

    def _primary_cta_text(self, stage: int) -> str:
        """Return one explicit default CTA per process stage."""
        return {
            1: "Primary: Enter to Merge",
            2: "Primary: Enter to Create Project",
            3: "Primary: Enter to Do Now",
            4: "Primary: Enter to Accept Suggestion",
        }.get(stage, "")

    def _next_step_hint(self, stage: int) -> str:
        """Return one-step-next guidance for process momentum."""
        return {
            1: "Next: Press 2 to move to Clustering.",
            2: "Next: Press 3 to move to 2-Min Drill.",
            3: "Next: Press 4 for Coach when this item is handled.",
            4: "Next: Press Esc to return after processing.",
        }.get(stage, "")

    def _update_stage_guidance(
        self,
        stage: int,
        *,
        primary: str | None = None,
        controls: str | None = None,
        next_step: str | None = None,
    ) -> None:
        """Refresh CTA and one-step guidance copy for the current stage."""
        self.query_one("#process-cta-text", Static).update(
            primary or self._primary_cta_text(stage)
        )
        controls_text = controls or "1-4: Jump stages │ ?: Help │ Esc: Back"
        next_text = next_step or self._next_step_hint(stage)
        help_parts = [controls_text]
        if next_text:
            help_parts.append(next_text)
        self.query_one("#process-help-text", Static).update(" │ ".join(help_parts))

    async def _load_coach_suggestion_async(self, title: str) -> None:
        suggestion = await asyncio.to_thread(coach_task, title)
        if not self.is_mounted or self._stage != 4:
            return
        self._coach_suggestion = suggestion
        suggestion_text = self._coach_suggestion or "(Add API key for AI suggestions)"
        self.query_one("#coach-suggestion-text", Static).update(suggestion_text)

    # Action handlers
    def action_stage1(self) -> None:
        """Go to stage 1."""
        self._go_stage(1)

    def action_stage2(self) -> None:
        """Go to stage 2."""
        self._go_stage(2)

    def action_stage3(self) -> None:
        """Go to stage 3."""
        self._go_stage(3)

    def action_stage4(self) -> None:
        """Go to stage 4."""
        self._go_stage(4)

    def action_primary(self) -> None:
        """Run the stage-specific primary CTA action."""
        if self._stage == 1:
            if self._dedup_pair:
                self.action_merge()
            else:
                self.action_stage2()
            return
        if self._stage == 2:
            if self._cluster_suggestions:
                self.action_create_project()
            else:
                self.action_stage3()
            return
        if self._stage == 3:
            asyncio.create_task(self._primary_stage3_async())
            return
        if self._stage == 4:
            asyncio.create_task(self._primary_stage4_async())

    async def _primary_stage3_async(self) -> None:
        """Run Stage 3 primary action without blocking the UI thread."""
        item = await asyncio.to_thread(self._engine.get_2min_current)
        if item:
            self.action_do_now()
        else:
            self.action_stage4()

    async def _primary_stage4_async(self) -> None:
        """Run Stage 4 primary action without blocking the UI thread."""
        item = await asyncio.to_thread(self._engine.get_coach_current)
        if item and self._coach_suggestion:
            self.action_accept()
        elif item:
            self.action_skip()
        else:
            self.action_go_back()

    def action_cursor_down(self) -> None:
        """Move cursor down in lists."""
        if self._stage == 2:
            opt_list = self.query_one("#cluster-list", OptionList)
            opt_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in lists."""
        if self._stage == 2:
            opt_list = self.query_one("#cluster-list", OptionList)
            opt_list.action_cursor_up()

    def action_merge(self) -> None:
        """Merge duplicate items (Stage 1)."""
        if self._stage == 1 and self._dedup_pair:
            a, b = self._dedup_pair
            asyncio.create_task(self._merge_async(a.id, b.id))

    async def _merge_async(self, keep_id: str, remove_id: str) -> None:
        await asyncio.to_thread(self._engine.dedup_merge, keep_id, remove_id)
        if self.is_mounted:
            self.notify("🔀 Merged items", severity="information", timeout=2)
            self._go_stage(1)

    def action_keep_both(self) -> None:
        """Keep both items (Stage 1)."""
        if self._stage == 1 and self._dedup_pair:
            self._engine.dedup_keep_both()
            self.notify("✅ Kept both items", timeout=2)
            self._go_stage(1)

    def action_do_now(self) -> None:
        """Do item now (Stage 3)."""
        if self._stage == 3:
            asyncio.create_task(self._do_now_async())

    async def _do_now_async(self) -> None:
        item = await asyncio.to_thread(self._engine.get_2min_current)
        if item and self.is_mounted:
            await asyncio.to_thread(self._engine.two_min_do_now, item.id)
            self._engine.two_min_advance()
            self.notify("⚡ Done!", severity="information", timeout=1)
            self._go_stage(3)

    def action_delete(self) -> None:
        """Delete item from 2-minute drill (Stage 3)."""
        if self._stage == 3:
            asyncio.create_task(self._delete_async())

    async def _delete_async(self) -> None:
        item = await asyncio.to_thread(self._engine.get_2min_current)
        if item and self.is_mounted:
            await asyncio.to_thread(self._engine.two_min_delete, item.id)
            self._engine.two_min_advance()
            self.notify("🗑️ Deleted", severity="warning", timeout=1)
            self._go_stage(3)

    def action_defer(self) -> None:
        """Defer item (Stage 3)."""
        if self._stage != 3:
            return
        asyncio.create_task(self._open_stage3_defer_async())

    async def _open_stage3_defer_async(self) -> None:
        item = await asyncio.to_thread(self._engine.get_2min_current)
        if not item:
            self.notify("No current item to defer", severity="warning", timeout=2)
            self._go_stage(3)
            return
        self.app.push_screen(
            DeferDialog(),
            callback=lambda result: self._apply_stage3_defer_result(item.id, result),
        )

    def _apply_stage3_defer_result(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Apply selected defer behavior for Stage 3."""
        asyncio.create_task(self._apply_stage3_defer_result_async(item_id, result))

    async def _apply_stage3_defer_result_async(
        self, item_id: str, result: dict[str, str] | None
    ) -> None:
        """Apply selected defer behavior for Stage 3 off the main thread."""
        if not result:
            return

        item = await asyncio.to_thread(self._engine.get_item, item_id)
        if not item:
            self.notify(
                "Item no longer exists. Refreshing…", severity="warning", timeout=2
            )
            self._go_stage(3)
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
            parsed = None
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

        self._engine.two_min_advance()
        self._go_stage(3)

    def action_create_project(self) -> None:
        """Create project from cluster (Stage 2)."""
        if self._stage == 2 and self._cluster_suggestions:
            opt_list = self.query_one("#cluster-list", OptionList)
            idx = opt_list.highlighted
            if idx is not None and 0 <= idx < len(self._cluster_suggestions):
                name, ids = self._cluster_suggestions[idx]
                asyncio.create_task(self._create_project_async(name, ids))

    async def _create_project_async(self, name: str, ids: list[str]) -> None:
        await asyncio.to_thread(self._engine.create_project, name, ids)
        if self.is_mounted:
            self.notify(f"📁 Created project: {name}", severity="information", timeout=2)
            self._go_stage(2)

    def action_accept(self) -> None:
        """Accept AI suggestion (Stage 4)."""
        if self._stage == 4 and self._coach_suggestion:
            asyncio.create_task(self._accept_async())

    async def _accept_async(self) -> None:
        item = await asyncio.to_thread(self._engine.get_coach_current)
        if item and self._coach_suggestion and self.is_mounted:
            await asyncio.to_thread(
                self._engine.coach_apply_suggestion, item.id, self._coach_suggestion
            )
            self._engine.coach_advance()
            self.notify("✨ Applied suggestion", severity="information", timeout=2)
            self._go_stage(4)

    def action_skip(self) -> None:
        """Skip current item."""
        if self._stage == 2:
            self._cluster_selected += 1
            self._go_stage(2)
        elif self._stage == 4:
            self._engine.coach_advance()
            self._go_stage(4)

    def action_go_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()

    def action_show_help(self) -> None:
        """Show help toast."""
        help_messages = {
            1: "Stage 1: Dedup\nm: Merge │ b: Keep Both\n1-4: Jump to stage",
            2: "Stage 2: Cluster\nc: Create Project │ n: Skip\nj/k: Navigate",
            3: "Stage 3: 2-Min\nd: Do Now │ f: Defer\nQuick wins!",
            4: "Stage 4: Coach\na: Accept │ n: Skip\nAI helps clarify tasks",
        }
        self.notify(
            help_messages.get(self._stage, ""),
            title=f"Help - Stage {self._stage}",
            timeout=5,
        )
