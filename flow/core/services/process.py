"""Process funnel service operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from flow.core.coach import estimate_duration, estimate_duration_heuristic, suggest_clusters
from flow.database.sqlite import SqliteDB
from flow.models import Item


class ProcessService:
    """Encapsulates dedup/cluster/2-minute/coach operations."""

    def __init__(self, db: SqliteDB) -> None:
        self._db = db

    def dedup_merge(self, keep_id: str, remove_id: str) -> None:
        keep = self._db.get_item(keep_id)
        remove = self._db.get_item(remove_id)
        if not keep or not remove:
            return
        updated = keep.model_copy(update={"title": keep.title + " / " + remove.title})
        self._db.update_item(updated)
        archived = remove.model_copy(update={"status": "archived"})
        self._db.update_item(archived)

    def get_cluster_suggestions(self, process_inbox: list[Item]) -> list[tuple[str, list[str]]]:
        items = [i for i in process_inbox if i.status != "archived"]
        if not items:
            return []
        titles = [i.title for i in items]
        suggestions = suggest_clusters(titles)
        return [
            (name, [items[idx].id for idx in indices]) for name, indices in suggestions
        ]

    def create_project(self, name: str, item_ids: list[str]) -> Item:
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
        return proj

    def two_min_items(
        self, process_inbox: list[Item], duration_cutoff_minutes: int = 15
    ) -> list[Item]:
        """Prioritize short tasks for the 2-minute drill."""
        items = [
            i for i in process_inbox if i.status != "archived" and i.type != "project"
        ]
        short: list[Item] = []
        unknown: list[Item] = []
        for item in items:
            if item.estimated_duration is None:
                unknown.append(item)
                continue
            if item.estimated_duration <= duration_cutoff_minutes:
                short.append(item)
        if short:
            return short[:20]
        return unknown[:20]

    def two_min_do_now(self, item_id: str) -> None:
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

    def two_min_delete(self, item_id: str) -> None:
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"status": "archived"}))

    def coach_apply_suggestion(
        self, item_id: str, new_title: str, auto_estimate_duration: bool = True
    ) -> None:
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        item = self._db.get_item(item_id)
        if item:
            updates: dict = {"title": new_title.strip()}
            if auto_estimate_duration and item.estimated_duration is None:
                duration = estimate_duration(new_title)
                if duration is None:
                    duration = estimate_duration_heuristic(new_title)
                updates["estimated_duration"] = duration
            self._db.update_item(item.model_copy(update=updates))

    def set_item_duration(self, item_id: str, duration_minutes: int) -> None:
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
