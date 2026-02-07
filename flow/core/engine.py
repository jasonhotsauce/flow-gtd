"""Main workflow: Capture -> Process -> Execute."""

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flow.config import get_settings
from flow.core.coach import (
    estimate_duration,
    estimate_duration_heuristic,
    suggest_clusters,
)
from flow.core.tagging import extract_tags
from flow.database.resources import ResourceDB
from flow.database.sqlite import SqliteDB
from flow.models import Item, Resource

logger = logging.getLogger(__name__)


class Engine:
    """Orchestrates capture, process funnel, and next-actions. Depends on Config + DB."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self._db_path = db_path or settings.db_path
        self._db = SqliteDB(self._db_path)
        self._db.init_db()
        self._resource_db = ResourceDB(self._db_path)
        self._resource_db.init_db()
        self._process_inbox: list[Item] = []
        self._dedup_index = 0
        self._two_min_index = 0
        self._coach_index = 0

    def capture(
        self,
        text: str,
        meta_payload: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        skip_auto_tag: bool = False,
    ) -> Item:
        """Quick capture: create inbox item and persist.

        Tasks are automatically tagged in the background using LLM for
        matching with saved resources.

        Args:
            text: The capture text (task description, note, etc.).
            meta_payload: Optional metadata dict to attach.
            tags: Optional explicit tags (skips auto-tagging).
            skip_auto_tag: If True, skip LLM auto-tagging entirely.

        Returns:
            The created Item.
        """
        item = Item(
            id=str(uuid.uuid4()),
            type="inbox",
            title=text.strip(),
            status="active",
            context_tags=tags or [],
            meta_payload=meta_payload or {},
        )
        self._db.insert_inbox(item)

        # Auto-tag in background if no explicit tags provided
        if not tags and not skip_auto_tag:
            self._schedule_auto_tagging(item.id, text)

        return item

    def _schedule_auto_tagging(self, item_id: str, text: str) -> None:
        """Schedule auto-tagging in a background thread.

        Args:
            item_id: ID of the item to tag.
            text: Text content to extract tags from.
        """

        def _run_tagging() -> None:
            try:
                existing_tags = self._resource_db.get_tag_names()
                tags = extract_tags(text, "text", existing_tags)
                if tags:
                    item = self._db.get_item(item_id)
                    if item:
                        # Merge with any existing tags
                        merged = list(dict.fromkeys(item.context_tags + tags))
                        updated = item.model_copy(update={"context_tags": merged})
                        self._db.update_item(updated)
                        # Update tag usage counts
                        for tag in tags:
                            self._resource_db.increment_tag_usage(tag)
            except (IOError, ValueError, RuntimeError) as e:
                logger.debug("Auto-tagging failed for item %s: %s", item_id, e)

        thread = threading.Thread(target=_run_tagging, daemon=True)
        thread.start()

    def list_inbox(self) -> list[Item]:
        """Return open inbox items (type='inbox', not archived, not done)."""
        return self._db.list_inbox()

    def get_resources_for_task(self, task_id: str) -> list[Resource]:
        """Get resources matching a task's tags.

        Args:
            task_id: ID of the task.

        Returns:
            List of Resource objects with matching tags.
        """
        item = self._db.get_item(task_id)
        if not item or not item.context_tags:
            return []
        return self._resource_db.find_resources_by_tags(item.context_tags)

    def get_resources_by_tags(self, tags: list[str]) -> list[Resource]:
        """Get resources matching the given tags.

        Args:
            tags: List of tag names to match.

        Returns:
            List of Resource objects with matching tags.
        """
        if not tags:
            return []
        return self._resource_db.find_resources_by_tags(tags)

    def get_item(self, item_id: str) -> Optional[Item]:
        """Return one item by id."""
        return self._db.get_item(item_id)

    def update_item(self, item: Item) -> None:
        """Persist changes to an item."""
        self._db.update_item(item)

    def next_actions(self, parent_id: Optional[str] = None) -> list[Item]:
        """Return active items for execution view (status=active). Project logic later."""
        return self._db.list_actions(status="active", parent_id=parent_id)

    # ---- Process Funnel ----
    def process_start(self) -> list[Item]:
        """Load inbox into working set for process funnel. Returns current inbox list."""
        self._process_inbox = self.list_inbox()
        self._dedup_index = 0
        self._two_min_index = 0
        self._coach_index = 0
        return self._process_inbox

    def process_inbox_items(self) -> list[Item]:
        """Return current process working set (inbox items being processed)."""
        if not self._process_inbox:
            self._process_inbox = self.list_inbox()
        return self._process_inbox

    def get_dedup_pair(self) -> Optional[tuple[Item, Item]]:
        """Return next pair for dedup (Stage 1), or None if fewer than 2 items."""
        items = [i for i in self._process_inbox if i.status != "archived"]
        while self._dedup_index + 1 < len(items):
            a, b = items[self._dedup_index], items[self._dedup_index + 1]
            self._dedup_index += 1
            return (a, b)
        return None

    def dedup_merge(self, keep_id: str, remove_id: str) -> None:
        """Merge remove into keep (combine titles), archive remove."""
        keep = self._db.get_item(keep_id)
        remove = self._db.get_item(remove_id)
        if not keep or not remove:
            return
        updated = keep.model_copy(update={"title": keep.title + " / " + remove.title})
        self._db.update_item(updated)
        archived = remove.model_copy(update={"status": "archived"})
        self._db.update_item(archived)
        self._process_inbox = self.list_inbox()

    def dedup_keep_both(self) -> None:
        """No-op; pair is skipped (already advanced in get_dedup_pair)."""

    def get_cluster_suggestions(self) -> list[tuple[str, list[str]]]:
        """Return suggested (project_name, [item_ids]) clusters."""
        items = [i for i in self._process_inbox if i.status != "archived"]
        if not items:
            return []
        titles = [i.title for i in items]
        suggestions = suggest_clusters(titles)
        return [
            (name, [items[idx].id for idx in indices]) for name, indices in suggestions
        ]

    def create_project(self, name: str, item_ids: list[str]) -> Item:
        """Create project and set children parent_id. Returns the new project Item."""
        proj = Item(
            id=str(uuid.uuid4()),
            type="project",
            title=name,
            status="active",
        )
        self._db.insert_inbox(proj)
        for iid in item_ids:
            item = self._db.get_item(iid)
            if item:
                child = item.model_copy(update={"parent_id": proj.id, "type": "action"})
                self._db.update_item(child)
        self._process_inbox = self.list_inbox()
        return proj

    def ungroup_items(self, item_ids: list[str]) -> None:
        """Clear parent_id and set type=action for given items."""
        for iid in item_ids:
            item = self._db.get_item(iid)
            if item:
                self._db.update_item(
                    item.model_copy(update={"parent_id": None, "type": "action"})
                )
        self._process_inbox = self.list_inbox()

    def get_2min_items(self) -> list[Item]:
        """Items for 2-min drill (Stage 3): short-title or first N."""
        items = [i for i in self._process_inbox if i.status != "archived"]
        return items[:20]

    def get_2min_current(self) -> Optional[Item]:
        """Current item in 2-min drill."""
        items = self.get_2min_items()
        if self._two_min_index < len(items):
            return items[self._two_min_index]
        return None

    def two_min_advance(self) -> None:
        """Advance to the next item in the 2-minute drill."""
        self._two_min_index += 1

    def two_min_do_now(self, item_id: str) -> None:
        """Mark item done."""
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(
                item.model_copy(
                    update={
                        "status": "done",
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )
        self._process_inbox = self.list_inbox()

    def two_min_defer(self, _item_id: str) -> None:
        """Keep as active (no change) or set waiting."""
        self._process_inbox = self.list_inbox()

    def get_coach_current(self) -> Optional[Item]:
        """Next item for coach (Stage 4)."""
        items = [
            i
            for i in self._process_inbox
            if i.status != "archived" and i.type != "project"
        ]
        if self._coach_index < len(items):
            return items[self._coach_index]
        return None

    def coach_advance(self) -> None:
        """Advance to the next item in the coach stage."""
        self._coach_index += 1

    def coach_apply_suggestion(
        self, item_id: str, new_title: str, auto_estimate_duration: bool = True
    ) -> None:
        """Apply AI suggestion to update item title.

        If auto_estimate_duration is True (default), also estimates and sets
        the task duration using LLM (with heuristic fallback).

        Args:
            item_id: ID of item to update.
            new_title: New title to apply (must not be empty).
            auto_estimate_duration: Whether to estimate duration automatically.

        Raises:
            ValueError: If new_title is empty or whitespace-only.
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")

        item = self._db.get_item(item_id)
        if item:
            updates: dict = {"title": new_title.strip()}

            # Estimate duration if not already set and auto-estimate is enabled
            if auto_estimate_duration and item.estimated_duration is None:
                duration = estimate_duration(new_title)
                if duration is None:
                    # Fallback to heuristic if LLM unavailable
                    duration = estimate_duration_heuristic(new_title)
                updates["estimated_duration"] = duration

            self._db.update_item(item.model_copy(update=updates))
        self._process_inbox = self.list_inbox()

    def set_item_duration(self, item_id: str, duration_minutes: int) -> None:
        """Set estimated duration for an item manually.

        Args:
            item_id: ID of item to update.
            duration_minutes: Duration in minutes (must be one of: 5, 15, 30, 60, 120).

        Raises:
            ValueError: If duration_minutes is not a valid duration value.
            ValueError: If item_id does not exist.
        """
        from flow.core.coach import VALID_DURATIONS

        if duration_minutes not in VALID_DURATIONS:
            raise ValueError(
                f"Duration must be one of {VALID_DURATIONS}, got {duration_minutes}"
            )

        item = self._db.get_item(item_id)
        if not item:
            raise ValueError(f"Item with id '{item_id}' not found")

        self._db.update_item(
            item.model_copy(update={"estimated_duration": duration_minutes})
        )

    def estimate_item_duration(
        self, item_id: str, use_llm: bool = True
    ) -> Optional[int]:
        """Estimate and set duration for an item.

        Args:
            item_id: ID of item to estimate.
            use_llm: If True, use LLM; otherwise use heuristics only.

        Returns:
            Estimated duration in minutes, or None if item not found.
        """
        item = self._db.get_item(item_id)
        if not item:
            return None

        if use_llm:
            duration = estimate_duration(item.title)
            if duration is None:
                duration = estimate_duration_heuristic(item.title)
        else:
            duration = estimate_duration_heuristic(item.title)

        self._db.update_item(item.model_copy(update={"estimated_duration": duration}))
        return duration

    # ---- Weekly Review ----
    def get_stale(self, days: int = 14) -> list[Item]:
        """Items older than days (suggest archiving)."""
        return self._db.list_stale(days=days)

    def get_someday_suggestions(self) -> list[Item]:
        """Items with status=someday (suggest resurfacing)."""
        return self._db.list_someday()

    def archive_item(self, item_id: str) -> None:
        """Set item status to archived."""
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"status": "archived"}))

    def resurface_item(self, item_id: str) -> None:
        """Set item status to active (from someday)."""
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"status": "active"}))

    def complete_item(self, item_id: str) -> None:
        """Set item status to done (mark as completed)."""
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(
                item.model_copy(
                    update={
                        "status": "done",
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )

    def weekly_report(self, days: int = 7) -> str:
        """Markdown/ASCII weekly report: completed items in the last days."""
        done = self._db.list_done_since(days=days)
        lines = [
            "# Flow Weekly Report",
            "",
            f"**Completed this week:** {len(done)} items",
            "",
            "## Done",
            "",
        ]
        for item in done:
            lines.append(f"- {item.title[:80]}{'...' if len(item.title) > 80 else ''}")
        return "\n".join(lines)
