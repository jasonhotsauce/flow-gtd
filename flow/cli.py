"""[Layer: Presentation] Typer CLI Commands."""

import typer

from flow.core.engine import Engine
from flow.tui.app import FlowApp
from flow.tui.screens.process import ProcessScreen
from flow.tui.screens.action.action import ActionScreen
from flow.tui.screens.review.review import ReviewScreen
from flow.config import get_settings
from flow.sync.reminders import sync_reminders_to_flow

app = typer.Typer(
    name="flow",
    help="Local-First, AI-Augmented GTD CLI for Senior Engineering Managers.",
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Launch TUI by default when no command is provided."""
    if ctx.invoked_subcommand is None:
        FlowApp().run()


def _do_capture(text: str, use_context: bool = True) -> None:
    import sys

    meta = None
    if use_context and sys.platform == "darwin":
        try:
            from flow.sync.context_hook import capture_context

            meta = capture_context()
        except Exception:
            pass
    engine = Engine()
    item = engine.capture(text, meta_payload=meta)
    typer.echo(f"Captured: {item.title[:60]}{'...' if len(item.title) > 60 else ''}")


@app.command()
def capture(
    text: str = typer.Argument(..., help="Quick capture text to inbox")
) -> None:
    """Capture a thought or task to the inbox."""
    _do_capture(text)


@app.command(name="c")
def c(text: str = typer.Argument(..., help="Quick capture (short alias)")) -> None:
    """Quick capture to inbox (alias for capture)."""
    _do_capture(text)


@app.command()
def tui() -> None:
    """Launch the interactive TUI for deep processing."""
    FlowApp().run()


@app.command()
def process() -> None:
    """Launch TUI Process Funnel (Dedup -> Cluster -> 2-Min -> Coach)."""
    FlowApp(initial_screen=ProcessScreen).run()


@app.command()
def next_cmd() -> None:
    """Show next actions (TUI Action screen)."""
    FlowApp(initial_screen=ActionScreen).run()


@app.command(name="next")
def next_() -> None:
    """Show next actions (alias for next_cmd)."""
    next_cmd()


@app.command()
def sync() -> None:
    """Sync Apple Reminders into Flow inbox (macOS only)."""
    settings = get_settings()
    _, msg = sync_reminders_to_flow(settings.db_path)
    typer.echo(msg)


@app.command()
def review() -> None:
    """Launch TUI Weekly Review (Stale, Someday, Report)."""
    FlowApp(initial_screen=ReviewScreen).run()


@app.command()
def report() -> None:
    """Print weekly report (velocity, completed items) to stdout."""
    engine = Engine()
    typer.echo(engine.weekly_report())


@app.command()
def version() -> None:
    """Show Flow version."""
    typer.echo("Flow GTD v0.1.0")
