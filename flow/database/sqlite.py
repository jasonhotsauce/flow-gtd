"""Relational wrapper for SQLite (tasks/items)."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flow.models import Item


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string, returning None for invalid input."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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
                    original_ek_id TEXT,
                    estimated_duration INTEGER
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status_type ON items(status, type)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parent ON items(parent_id)")
            # Migration: add estimated_duration column if missing
            self._migrate_add_estimated_duration(conn)
            # Migration: add updated_at column if missing
            self._migrate_add_updated_at(conn)
            self._init_index_jobs(conn)
            conn.commit()

    def _migrate_add_estimated_duration(self, conn: sqlite3.Connection) -> None:
        """Add estimated_duration column if it doesn't exist (migration)."""
        cursor = conn.execute("PRAGMA table_info(items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "estimated_duration" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN estimated_duration INTEGER")

    def _migrate_add_updated_at(self, conn: sqlite3.Connection) -> None:
        """Add updated_at column if it doesn't exist (migration)."""
        cursor = conn.execute("PRAGMA table_info(items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN updated_at DATETIME")
            conn.execute(
                "UPDATE items SET updated_at = created_at WHERE updated_at IS NULL"
            )

    def _init_index_jobs(self, conn: sqlite3.Connection) -> None:
        """Create durable index queue table for background semantic indexing."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS index_jobs (
                    id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_index_jobs_status_created "
                "ON index_jobs(status, created_at)"
            )
        except sqlite3.OperationalError:
            # Read-only databases (e.g., certain test harnesses) should still load.
            return

    def insert_inbox(self, item: Item) -> None:
        """Insert a single inbox item (type=inbox, status=active)."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO items (id, type, title, status, context_tags, parent_id,
                                  created_at, due_date, meta_payload, original_ek_id,
                                  estimated_duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item.estimated_duration,
                ),
            )
            conn.commit()

    def list_inbox(self) -> list[Item]:
        """Return active inbox items that are not assigned to a project."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE type = 'inbox' AND status = 'active' "
                "AND parent_id IS NULL ORDER BY created_at ASC"
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
                                meta_payload=?, original_ek_id=?, estimated_duration=?,
                                updated_at=?
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
                    item.estimated_duration,
                    _iso(item.updated_at),
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

    def list_projects(self, status: str = "active") -> list[Item]:
        """Return projects (type='project') by status for project list view."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE type = 'project' AND status = ? "
                "ORDER BY created_at ASC",
                (status,),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def list_stale(self, days: int = 14) -> list[Item]:
        """Return items where created_at is older than days (for review)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE created_at < datetime('now', ?) "
                "AND status NOT IN ('archived', 'done') ORDER BY created_at ASC",
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

    def list_done_since(self, days: int = 7) -> list[Item]:
        """Return items completed (status='done') within the last days (by updated_at)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items WHERE status = 'done' AND updated_at >= "
                "datetime('now', ?) ORDER BY updated_at DESC",
                (f"-{days} days",),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def list_actions_by_duration(
        self,
        max_duration: Optional[int] = None,
        min_duration: Optional[int] = None,
        status: str = "active",
    ) -> list[Item]:
        """Return active items filtered by estimated_duration range (for Focus Mode)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM items WHERE status = ?"
            params: list = [status]

            if max_duration is not None:
                query += " AND (estimated_duration IS NULL OR estimated_duration <= ?)"
                params.append(max_duration)
            if min_duration is not None:
                query += " AND (estimated_duration IS NULL OR estimated_duration >= ?)"
                params.append(min_duration)

            query += " ORDER BY created_at ASC"
            rows = conn.execute(query, params).fetchall()
        return [_row_to_item(r) for r in rows]

    def enqueue_index_job(
        self,
        resource_id: str,
        content_type: str,
        source: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> str:
        """Enqueue a background semantic-indexing job."""
        job_id = str(uuid.uuid4())
        now = _iso(datetime.now(timezone.utc))
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO index_jobs (
                    id, resource_id, content_type, source, title, summary,
                    status, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
                """,
                (job_id, resource_id, content_type, source, title, summary, now, now),
            )
            conn.commit()
        return job_id

    def list_index_jobs(self, status: str = "pending", limit: int = 20) -> list[dict]:
        """List queued indexing jobs by status."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM index_jobs WHERE status = ? ORDER BY created_at ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_index_job_status(
        self, job_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Update queue job status and optional error string."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE index_jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, _iso(datetime.now(timezone.utc)), job_id),
            )
            conn.commit()


def _row_to_item(row: sqlite3.Row) -> Item:
    """Convert database row to Item, handling malformed data gracefully."""
    # Parse JSON fields with fallback for malformed data
    try:
        context_tags = json.loads(row["context_tags"] or "[]")
    except json.JSONDecodeError:
        context_tags = []

    try:
        meta_payload = json.loads(row["meta_payload"] or "{}")
    except json.JSONDecodeError:
        meta_payload = {}

    return Item(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        status=row["status"],
        context_tags=context_tags,
        parent_id=row["parent_id"],
        created_at=_parse_dt(row["created_at"]),
        due_date=_parse_dt(row["due_date"]),
        meta_payload=meta_payload,
        original_ek_id=row["original_ek_id"],
        estimated_duration=row["estimated_duration"],
        updated_at=_parse_dt(row["updated_at"]) if "updated_at" in row.keys() else None,
    )
