"""Relational wrapper for SQLite (tasks/items)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from flow.models import Item


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class SqliteDB:
    """SQLite wrapper for items table. All I/O stays in this module."""

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def init_db(self) -> None:
        """Create items table and indexes if they do not exist."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    title TEXT,
                    status TEXT,
                    context_tags TEXT,
                    parent_id TEXT,
                    created_at DATETIME,
                    due_date DATETIME,
                    meta_payload TEXT,
                    original_ek_id TEXT
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status_type ON items(status, type)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parent ON items(parent_id)")
            conn.commit()

    def insert_inbox(self, item: Item) -> None:
        """Insert a single inbox item (type=inbox, status=active)."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO items (id, type, title, status, context_tags, parent_id,
                                  created_at, due_date, meta_payload, original_ek_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.type,
                    item.title,
                    item.status,
                    json.dumps(item.context_tags),
                    item.parent_id,
                    _iso(item.created_at),
                    _iso(item.due_date),
                    json.dumps(item.meta_payload),
                    item.original_ek_id,
                ),
            )
            conn.commit()

    def list_inbox(self) -> list[Item]:
        """Return all items with type='inbox'."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE type = 'inbox' and status != 'archived' "
                "ORDER BY created_at ASC"
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def get_item(self, item_id: str) -> Optional[Item]:
        """Return one item by id or None."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return _row_to_item(row) if row else None

    def get_item_by_ek_id(self, original_ek_id: str) -> Optional[Item]:
        """Return one item by Apple EventKit id (original_ek_id) or None."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM items WHERE original_ek_id = ?", (original_ek_id,)
            ).fetchone()
        return _row_to_item(row) if row else None

    def update_item(self, item: Item) -> None:
        """Update an existing item by id."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE items SET type=?, title=?, status=?, context_tags=?,
                                parent_id=?, created_at=?, due_date=?,
                                meta_payload=?, original_ek_id=?
                WHERE id = ?
                """,
                (
                    item.type,
                    item.title,
                    item.status,
                    json.dumps(item.context_tags),
                    item.parent_id,
                    _iso(item.created_at),
                    _iso(item.due_date),
                    json.dumps(item.meta_payload),
                    item.original_ek_id,
                    item.id,
                ),
            )
            conn.commit()

    def list_actions(
        self,
        status: str = "active",
        parent_id: Optional[str] = None,
    ) -> list[Item]:
        """Return items by status (and optional parent_id). For next-actions view."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            if parent_id is not None:
                rows = conn.execute(
                    "SELECT * FROM items WHERE status = ? AND parent_id = ? "
                    "ORDER BY created_at ASC",
                    (status, parent_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM items WHERE status = ? ORDER BY created_at ASC",
                    (status,),
                ).fetchall()
        return [_row_to_item(r) for r in rows]

    def list_stale(self, days: int = 14) -> list[Item]:
        """Return items where created_at is older than days (for review)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE created_at < datetime('now', ?) "
                "AND status != 'archived' ORDER BY created_at ASC",
                (f"-{days} days",),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def list_someday(self) -> list[Item]:
        """Return items with status='someday'."""
        return self.list_actions(status="someday")

    def list_done(self, limit: int = 100) -> list[Item]:
        """Return recently completed items (status='done') for report."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE status = 'done' "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_item(r) for r in rows]


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        status=row["status"],
        context_tags=json.loads(row["context_tags"] or "[]"),
        parent_id=row["parent_id"],
        created_at=_parse_dt(row["created_at"]),
        due_date=_parse_dt(row["due_date"]),
        meta_payload=json.loads(row["meta_payload"] or "{}"),
        original_ek_id=row["original_ek_id"],
    )
