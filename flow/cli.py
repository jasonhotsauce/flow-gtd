"""[Layer: Presentation] Typer CLI Commands."""

from importlib.metadata import PackageNotFoundError, version as get_package_version
from typing import TYPE_CHECKING, Optional, Type

import typer

from flow.core.engine import Engine
from flow.tui.app import FlowApp
from flow.tui.screens.process import ProcessScreen
from flow.tui.screens.action.action import ActionScreen
from flow.tui.screens.review.review import ReviewScreen
from flow.tui.screens.focus.focus import FocusScreen
from flow.config import get_settings
from flow.sync.reminders import sync_reminders_to_flow

if TYPE_CHECKING:
    from textual.screen import Screen


def _get_version() -> str:
    """Get version from package metadata (single source of truth: pyproject.toml)."""
    try:
        return get_package_version("flow-gtd")
    except PackageNotFoundError:
        return "0.0.0-dev"


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"flow-gtd {_get_version()}")
        raise typer.Exit()


app = typer.Typer(
    name="flow",
    help="Local-First, AI-Augmented GTD CLI for Senior Engineering Managers.",
)


def _check_onboarding() -> bool:
    """Check if onboarding is needed and run wizard if so.

    Returns:
        True if onboarding completed successfully, False if user quit.

    Note:
        Uses lazy imports to avoid circular dependencies:
        - cli.py imports from tui.app which may import from core
        - core uses llm.config for LLM configuration
        - Lazy importing breaks the import cycle and defers loading
          until actually needed at runtime.
    """
    # Lazy import: Prevents circular import with core layer
    from flow.utils.llm.config import is_onboarding_completed

    if is_onboarding_completed():
        return True

    # Lazy import: OnboardingApp has heavy TUI dependencies
    from flow.tui.onboarding.app import OnboardingApp

    result = OnboardingApp().run()
    return result is True


def _launch_tui(initial_screen: "Optional[Type[Screen]]" = None) -> None:
    """Launch TUI with onboarding check.

    Args:
        initial_screen: Optional Textual Screen class to launch.
            Defaults to InboxScreen if not specified.

    Raises:
        typer.Exit: If user quits during onboarding.
    """
    if not _check_onboarding():
        raise typer.Exit(0)
    FlowApp(initial_screen=initial_screen).run()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Launch TUI by default when no command is provided."""
    if ctx.invoked_subcommand is None:
        _launch_tui()


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
    _launch_tui()


@app.command()
def process() -> None:
    """Launch TUI Process Funnel (Dedup -> Cluster -> 2-Min -> Coach)."""
    _launch_tui(ProcessScreen)


@app.command()
def next_cmd() -> None:
    """Show next actions (TUI Action screen)."""
    _launch_tui(ActionScreen)


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
    _launch_tui(ReviewScreen)


@app.command()
def focus() -> None:
    """Launch Focus Mode - AI selects best task for your time window.

    Smart Dispatcher analyzes your calendar to determine available time,
    then selects the optimal task:
    - < 30 mins: Quick Wins (short tasks, @admin)
    - > 2 hours: Deep Work (high-energy tasks)
    - Otherwise: Standard priority order
    """
    _launch_tui(FocusScreen)


@app.command()
def report() -> None:
    """Print weekly report (velocity, completed items) to stdout."""
    engine = Engine()
    typer.echo(engine.weekly_report())


@app.command()
def version() -> None:
    """Show Flow version."""
    typer.echo(f"flow-gtd {_get_version()}")
