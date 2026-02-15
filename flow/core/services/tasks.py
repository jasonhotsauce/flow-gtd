"""Task-oriented service operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flow.database.sqlite import SqliteDB
from flow.models import Item


class TaskService:
    """Encapsulates item CRUD and task-state transitions."""

    def __init__(self, db: SqliteDB) -> None:
        self._db = db

    def get_item(self, item_id: str) -> Optional[Item]:
        return self._db.get_item(item_id)

    def update_item(self, item: Item) -> None:
        self._db.update_item(item)

    def complete_item(self, item_id: str) -> None:
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

    def archive_item(self, item_id: str) -> None:
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"status": "archived"}))

    def resurface_item(self, item_id: str) -> None:
        item = self._db.get_item(item_id)
        if item:
            self._db.update_item(item.model_copy(update={"status": "active"}))
