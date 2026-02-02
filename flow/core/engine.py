"""Main workflow: Capture -> Process -> Execute."""

import uuid
from pathlib import Path
from typing import Optional

from flow.config import get_settings
from flow.database.sqlite import SqliteDB
from flow.database.vectors import schedule_auto_index
from flow.models import Item
from flow.core.coach import suggest_clusters


class Engine:
    """Orchestrates capture, process funnel, and next-actions. Depends on Config + DB."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self._db_path = db_path or settings.db_path
        self._db = SqliteDB(self._db_path)
        self._db.init_db()
        self._process_inbox: list[Item] = []
        self._dedup_index = 0
        self._two_min_index = 0
        self._coach_index = 0

    def capture(self, text: str, meta_payload: Optional[dict] = None) -> Item:
        """Quick capture: create inbox item and persist. Returns the created Item."""
        item = Item(
            id=str(uuid.uuid4()),
            type="inbox",
            title=text.strip(),
            status="active",
            meta_payload=meta_payload or {},
        )
        self._db.insert_inbox(item)
        settings = get_settings()
        schedule_auto_index(text, settings.chroma_path)
        return item

    def list_inbox(self) -> list[Item]:
        """Return all inbox items."""
        return self._db.list_inbox()

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
            self._db.update_item(item.model_copy(update={"status": "done"}))
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

    def coach_apply_suggestion(self, item_id: str, new_title: str) -> None:
        """Apply AI suggestion to update item title."""
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"title": new_title.strip()}))
        self._process_inbox = self.list_inbox()

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
            self._db.update_item(item.model_copy(update={"status": "done"}))

    def weekly_report(self, limit: int = 50) -> str:
        """Markdown/ASCII weekly report: velocity (completed count), completed items."""
        done = self._db.list_done(limit=limit)
        lines = [
            "# Flow Weekly Report",
            "",
            f"**Completed:** {len(done)} items",
            "",
            "## Done",
            "",
        ]
        for item in done:
            lines.append(f"- {item.title[:80]}{'...' if len(item.title) > 80 else ''}")
        return "\n".join(lines)
