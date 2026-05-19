"""Memory service operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flow.database.sqlite import SqliteDB
from flow.models import MemoryEntry


class MemoryService:
    """Encapsulates inspectable memory CRUD operations."""

    def __init__(self, db: SqliteDB) -> None:
        self._db = db

    def create_entry(
        self,
        *,
        kind: str,
        scope: str,
        value: str,
        source: str,
        confidence: float,
        scope_ref: str | None = None,
    ) -> MemoryEntry:
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            kind=kind,
            scope=scope,
            scope_ref=scope_ref,
            value=value.strip(),
            source=source,
            confidence=confidence,
            enabled=True,
            created_at=now,
            updated_at=now,
            last_confirmed_at=now,
        )
        self._db.insert_memory_entry(entry)
        return entry

    def get_entry(self, memory_id: str) -> MemoryEntry | None:
        return self._db.get_memory_entry(memory_id)

    def list_entries(
        self,
        *,
        query: str | None = None,
        include_disabled: bool = True,
    ) -> list[MemoryEntry]:
        return self._db.list_memory_entries(
            query=query,
            include_disabled=include_disabled,
        )

    def update_entry(self, memory_id: str, *, value: str) -> MemoryEntry:
        existing = self._db.get_memory_entry(memory_id)
        if existing is None:
            raise ValueError("Memory entry does not exist")
        updated = existing.model_copy(
            update={
                "value": value.strip(),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._db.update_memory_entry(updated)
        return updated

    def set_entry_enabled(self, memory_id: str, *, enabled: bool) -> MemoryEntry:
        existing = self._db.get_memory_entry(memory_id)
        if existing is None:
            raise ValueError("Memory entry does not exist")
        updated = existing.model_copy(
            update={
                "enabled": enabled,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._db.update_memory_entry(updated)
        return updated

    def delete_entry(self, memory_id: str) -> None:
        self._db.delete_memory_entry(memory_id)
