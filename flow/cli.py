"""[Layer: Presentation] Typer CLI Commands."""

import re
import multiprocessing
import uuid
from importlib.metadata import PackageNotFoundError, version as get_package_version
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Type, TypedDict

import typer

from flow.config import get_settings
from flow.core.engine import Engine
from flow.core.tagging import (
    extract_tags_from_file,
    extract_tags_from_url,
    extract_tags,
    normalize_tag,
    parse_user_tags,
)
from flow.database.resources import ResourceDB
from flow.models import ContentType, Resource
from flow.sync.reminders import get_reminder_auth_status, sync_reminders_to_flow
from flow.tui.app import FlowApp
from flow.tui.screens.action.action import ActionScreen
from flow.tui.screens.focus.focus import FocusScreen
from flow.tui.screens.process import ProcessScreen
from flow.tui.screens.projects.projects import ProjectsScreen
from flow.tui.screens.review.review import ReviewScreen

if TYPE_CHECKING:
    from textual.screen import Screen

# URL pattern for content type detection
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _kickoff_index_worker(db_path: Path) -> None:
    """Process pending index jobs asynchronously."""
    try:
        Engine(db_path=db_path).process_index_jobs(limit=20)
    except Exception:
        # Best-effort background indexing; foreground save must not fail.
        return


def _start_index_worker_process(db_path: Path) -> None:
    """Start queue processing in a detached process that outlives CLI exit."""
    try:
        process = multiprocessing.Process(
            target=_kickoff_index_worker,
            args=(db_path,),
            daemon=False,
        )
        process.start()
    except Exception:
        # Best-effort background indexing; foreground save must not fail.
        return


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


class InboxStartupContext(TypedDict):
    """Startup hints passed from CLI onboarding into Inbox."""

    highlighted_item_id: str
    show_first_value_hint: bool


def _build_startup_context_from_onboarding(
    onboarding_result: dict[str, object],
) -> InboxStartupContext | None:
    """Create Inbox startup context from onboarding first-capture outcome."""
    first_capture = onboarding_result.get("first_capture")
    if not isinstance(first_capture, dict):
        return None

    action = first_capture.get("action")
    text = first_capture.get("text")
    if action != "submit" or not isinstance(text, str):
        return None

    capture_text = text.strip()
    if not capture_text:
        return None

    try:
        created_item = Engine().capture(capture_text)
    except Exception:
        # First-capture handoff is optional; continue launching app on failure.
        return None
    return {
        "highlighted_item_id": created_item.id,
        "show_first_value_hint": True,
    }


def _check_onboarding() -> tuple[bool, InboxStartupContext | None]:
    """Check if onboarding is needed and run wizard if so.

    Returns:
        Tuple of (completed, inbox startup context).

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
        return True, None

    # Lazy import: OnboardingApp has heavy TUI dependencies
    from flow.tui.onboarding.app import OnboardingApp

    onboarding_app = OnboardingApp()
    result = onboarding_app.run()
    if result is not True:
        return False, None

    onboarding_result = onboarding_app.get_onboarding_result()
    startup_context = _build_startup_context_from_onboarding(onboarding_result)
    return True, startup_context


def _launch_tui(initial_screen: "Optional[Type[Screen]]" = None) -> None:
    """Launch TUI with onboarding check.

    Args:
        initial_screen: Optional Textual Screen class to launch.
            Defaults to InboxScreen if not specified.

    Raises:
        typer.Exit: If user quits during onboarding.
    """
    onboarding_completed, startup_context = _check_onboarding()
    if not onboarding_completed:
        raise typer.Exit(0)
    FlowApp(initial_screen=initial_screen, startup_context=startup_context).run()


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


def _do_capture(
    text: str,
    use_context: bool = True,
    tags: Optional[list[str]] = None,
    skip_auto_tag: bool = False,
) -> None:
    import sys

    meta = None
    if use_context and sys.platform == "darwin":
        try:
            from flow.sync.context_hook import capture_context

            meta = capture_context()
        except (ImportError, OSError):
            pass
    engine = Engine()
    # Block on auto-tagging so tags are written before CLI exits (daemon thread would be killed)
    def on_tagging_start() -> None:
        typer.echo("Tagging...")

    item = engine.capture(
        text,
        meta_payload=meta,
        tags=tags,
        skip_auto_tag=skip_auto_tag,
        block_auto_tag=True,
        on_tagging_start=on_tagging_start if (not tags and not skip_auto_tag) else None,
    )
    # Refetch so we show auto-applied tags (capture() returns before tagging updates the item)
    if not tags and not skip_auto_tag:
        updated = engine.get_item(item.id)
        if updated:
            item = updated
    typer.echo(f"Captured: {item.title[:60]}{'...' if len(item.title) > 60 else ''}")
    if item.context_tags:
        typer.echo(f"Tags: {', '.join(item.context_tags)}")
    elif tags:
        typer.echo(f"Tags: {', '.join(tags)}")


@app.command()
def capture(
    text: str = typer.Argument(..., help="Quick capture text to inbox"),
    private: bool = typer.Option(
        False,
        "--private",
        "-p",
        help="Skip auto-tagging (for sensitive content)",
    ),
    tags_opt: Optional[str] = typer.Option(
        None,
        "--tags",
        "-t",
        help="Comma-separated tags (skips auto-tagging)",
    ),
) -> None:
    """Capture a thought or task to the inbox.

    Tasks are automatically tagged for resource matching unless
    --private or --tags is specified.
    """
    tags = [normalize_tag(t) for t in tags_opt.split(",") if t.strip()] if tags_opt else None
    _do_capture(text, tags=tags, skip_auto_tag=private)


@app.command(name="c")
def c(
    text: str = typer.Argument(..., help="Quick capture (short alias)"),
    private: bool = typer.Option(False, "--private", "-p", help="Skip auto-tagging"),
) -> None:
    """Quick capture to inbox (alias for capture)."""
    _do_capture(text, skip_auto_tag=private)


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


@app.command()
def projects() -> None:
    """Show project list (GTD review and proceed)."""
    _launch_tui(ProjectsScreen)


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


@app.command(name="sync-status")
def sync_status() -> None:
    """Check Reminders authorization status (macOS only)."""
    status_code, status_desc = get_reminder_auth_status()
    typer.echo(f"Reminders Authorization: {status_desc}")
    if status_code == 0:  # Not Determined
        typer.echo("\nTo grant access, run 'flow sync' from Terminal.app")
    elif status_code == 2:  # Denied
        typer.echo("\nTo fix: System Settings → Privacy & Security → Reminders")
        typer.echo(
            "Enable access for your terminal app, or run: tccutil reset Reminders"
        )


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


def _detect_content_type(content: str) -> ContentType:
    """Detect if content is a URL, file path, or plain text."""
    if _URL_RE.match(content):
        return "url"
    # Check if it looks like a file path
    path = Path(content.strip())
    if path.exists() or (
        len(content) < 500
        and ("/" in content or "\\" in content)
        and not content.startswith("http")
    ):
        return "file"
    return "text"


def _fetch_url_metadata(url: str) -> tuple[Optional[str], Optional[str]]:
    """Fetch title and content preview from URL.

    Returns:
        Tuple of (title, content_preview) or (None, None) on failure.
    """
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None

        # Extract metadata for title
        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata else None

        # Extract content preview
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        preview = content[:500] if content else None

        return title, preview
    except (ImportError, IOError, ValueError, RuntimeError):
        return None, None


def _extract_file_content(path: Path, max_chars: int = 5000) -> Optional[str]:
    """Extract lightweight local file content for semantic indexing."""
    try:
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml"):
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return None
            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages[:5]:
                chunks.append(page.extract_text() or "")
            return "\n".join(chunks).strip()[:max_chars] or None
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return None


def _interactive_tag_selection(existing_tags: list[str]) -> list[str]:
    """Interactive tag selection for private mode.

    Args:
        existing_tags: List of existing tags to choose from.

    Returns:
        List of selected/created tags.
    """
    if existing_tags:
        typer.echo("\nExisting tags:")
        for i, tag in enumerate(existing_tags[:20], 1):
            typer.echo(f"  {i}. {tag}")
        if len(existing_tags) > 20:
            typer.echo(f"  ... and {len(existing_tags) - 20} more")
    else:
        typer.echo("\nNo existing tags yet.")

    typer.echo("\nEnter tags (comma-separated numbers, names, or NEW:tag-name):")
    user_input = typer.prompt("Tags", default="")

    return parse_user_tags(user_input, existing_tags)


@app.command()
def save(
    content: str = typer.Argument(..., help="URL, file path, or text to save"),
    private: bool = typer.Option(
        False,
        "--private",
        "-p",
        help="Manual tag selection (no LLM, content stays local)",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        "-t",
        help="Comma-separated tags (skips LLM auto-tagging)",
    ),
) -> None:
    """Save a resource (URL, file, or text) with automatic tagging.

    Examples:
        flow save https://docs.example.com/guide
        flow save ~/Documents/spec.pdf
        flow save "OAuth2 best practices: use PKCE for mobile"
        flow save https://internal.com/doc --private
        flow save https://example.com --tags "api,backend"
    """
    settings = get_settings()
    resource_db = ResourceDB(settings.db_path)
    resource_db.init_db()

    # Detect content type
    content_type = _detect_content_type(content)

    # Check for duplicate
    existing = resource_db.get_resource_by_source(content)
    if existing:
        typer.echo(f"Resource already saved (updating tags): {content[:60]}...")
        resource = existing
    else:
        resource = Resource(
            id=str(uuid.uuid4()),
            content_type=content_type,
            source=content,
            tags=[],
        )

    # Get title and preview for URLs
    title: Optional[str] = None
    preview: Optional[str] = None
    if content_type == "url" and not private:
        typer.echo("Fetching URL metadata...")
        title, preview = _fetch_url_metadata(content)
        if title:
            resource.title = title
        if preview:
            resource.summary = preview[:200]
            resource.raw_content = preview

    # Get file content preview
    if content_type == "file":
        try:
            path = Path(content)
            if path.exists() and path.is_file():
                resource.title = path.name
                file_content = _extract_file_content(path)
                if file_content:
                    preview = file_content[:500]
                    resource.summary = preview[:200]
                    resource.raw_content = file_content
        except (OSError, UnicodeDecodeError):
            pass

    # For text content, use first 200 chars as summary
    if content_type == "text":
        resource.summary = content[:200]
        resource.raw_content = content[:5000]
        preview = content

    # Determine tags
    existing_tags = resource_db.get_tag_names()
    final_tags: list[str] = []

    if tags:
        # User specified tags directly
        final_tags = [normalize_tag(t) for t in tags.split(",") if t.strip()]
        typer.echo(f"Using specified tags: {', '.join(final_tags)}")
    elif private:
        # Interactive tag selection
        final_tags = _interactive_tag_selection(existing_tags)
        if not final_tags:
            typer.echo("No tags selected. Resource saved without tags.")
    else:
        # Auto-tag with LLM
        typer.echo("Extracting tags...")
        if content_type == "url":
            final_tags = extract_tags_from_url(content, title, preview, existing_tags)
        elif content_type == "file":
            final_tags = extract_tags_from_file(content, preview, existing_tags)
        else:
            final_tags = extract_tags(content, "text", existing_tags)

        if final_tags:
            typer.echo(f"Auto-tagged: {', '.join(final_tags)}")
        else:
            typer.echo("Could not extract tags automatically.")

    # Update resource tags (merge with existing if updating)
    if existing:
        merged_tags = list(dict.fromkeys(resource.tags + final_tags))
        resource.tags = merged_tags
    else:
        resource.tags = final_tags

    # Save/update resource
    if existing:
        resource_db.update_resource(resource)
    else:
        resource_db.insert_resource(resource)

    # Update tag usage counts
    for tag in final_tags:
        resource_db.increment_tag_usage(tag)

    typer.echo(f"Saved: {resource.title or content[:50]}...")
    if resource.tags:
        typer.echo(f"Tags: {', '.join(resource.tags)}")

    # Enqueue local semantic indexing (non-blocking).
    try:
        Engine(db_path=settings.db_path).enqueue_resource_index(
            resource_id=resource.id,
            content_type=resource.content_type,
            source=resource.source,
            title=resource.title,
            summary=resource.summary,
        )
        _start_index_worker_process(settings.db_path)
    except Exception:
        pass


@app.command()
def resources(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results"),
) -> None:
    """List saved resources."""
    settings = get_settings()
    resource_db = ResourceDB(settings.db_path)
    resource_db.init_db()

    if tag:
        items = resource_db.find_resources_by_tags([tag])[:limit]
    else:
        items = resource_db.list_resources(limit=limit)

    if not items:
        typer.echo("No resources saved yet. Use 'flow save <url>' to add some.")
        return

    typer.echo(f"\nResources ({len(items)}):\n")
    for r in items:
        type_icon = {"url": "🔗", "file": "📄", "text": "📝"}.get(r.content_type, "📎")
        title = r.title or r.source[:50]
        tags_str = f" [{', '.join(r.tags)}]" if r.tags else ""
        typer.echo(f"  {type_icon} {title}{tags_str}")


@app.command(name="tags")
def list_tags() -> None:
    """List all tags with usage counts."""
    settings = get_settings()
    resource_db = ResourceDB(settings.db_path)
    resource_db.init_db()

    all_tags = resource_db.list_tags()

    if not all_tags:
        typer.echo("No tags yet. Save some resources to create tags.")
        return

    typer.echo(f"\nTags ({len(all_tags)}):\n")
    for t in all_tags:
        typer.echo(f"  {t.name} ({t.usage_count} uses)")
