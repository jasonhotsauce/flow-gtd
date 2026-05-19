"""Relational wrapper for SQLite (tasks/items)."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

from flow.models import (
    AssistantAgentContract,
    AssistantAuditStep,
    AssistantProposal,
    AssistantTurn,
    Item,
    MemoryEntry,
)


DailyPlanBucket = Literal["top", "bonus"]


class DailyPlanEntryInput(TypedDict):
    item_id: str
    bucket: DailyPlanBucket
    position: int


class DailyPlanEntryRecord(TypedDict):
    item: Item
    bucket: DailyPlanBucket
    position: int


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
            self._init_daily_plan_entries(conn)
            self._init_daily_recap_status(conn)
            self._init_assistant_turns(conn)
            self._init_assistant_audit_steps(conn)
            self._init_memory_entries(conn)
            self._init_native_workflow_tables(conn)
            self._migrate_legacy_items_to_native_workflow(conn)
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

    def _init_daily_plan_entries(self, conn: sqlite3.Connection) -> None:
        """Create daily plan table for Top 3 / Bonus selections."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_plan_entries (
                    plan_date TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (plan_date, item_id),
                    FOREIGN KEY (item_id) REFERENCES items(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_plan_date_bucket_position "
                "ON daily_plan_entries(plan_date, bucket, position)"
            )
        except sqlite3.OperationalError:
            return

    def _init_daily_recap_status(self, conn: sqlite3.Connection) -> None:
        """Create recap-status storage for explicit end-of-day acknowledgement.

        The table name remains `daily_wrap_status` for backward compatibility.
        """
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_wrap_status (
                    plan_date TEXT PRIMARY KEY,
                    wrapped_at DATETIME NOT NULL
                )
                """
            )
        except sqlite3.OperationalError:
            return

    def _init_assistant_turns(self, conn: sqlite3.Connection) -> None:
        """Create assistant turn storage."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_turns (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    route TEXT NOT NULL,
                    proposal_json TEXT,
                    proposal_status TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assistant_turns_created_at "
                "ON assistant_turns(created_at DESC)"
            )
        except sqlite3.OperationalError:
            return

    def _init_assistant_audit_steps(self, conn: sqlite3.Connection) -> None:
        """Create assistant audit-step storage."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_audit_steps (
                    id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (turn_id) REFERENCES assistant_turns(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assistant_audit_turn_created "
                "ON assistant_audit_steps(turn_id, created_at ASC)"
            )
        except sqlite3.OperationalError:
            return

    def _init_memory_entries(self, conn: sqlite3.Connection) -> None:
        """Create inspectable memory storage."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    scope_ref TEXT,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    last_confirmed_at DATETIME
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_entries_kind_scope "
                "ON memory_entries(kind, scope)"
            )
        except sqlite3.OperationalError:
            return

    def _init_native_workflow_tables(self, conn: sqlite3.Connection) -> None:
        """Create normalized workflow tables for the native product contract."""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS raw_captures (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS inbox_items (
                id TEXT PRIMARY KEY,
                raw_capture_id TEXT NOT NULL,
                origin_type TEXT NOT NULL,
                inbox_state TEXT NOT NULL,
                source_ref TEXT,
                imported_at DATETIME,
                task_id TEXT,
                clarified_task_id TEXT,
                clarified_project_id TEXT,
                clarified_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                project_id TEXT,
                source_inbox_item_id TEXT,
                time_sensitivity TEXT NOT NULL,
                effort_band TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reminder_links (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                sync_status TEXT NOT NULL,
                conflict_status TEXT NOT NULL,
                last_synced_at DATETIME,
                source_modified_at DATETIME,
                tombstoned_at DATETIME
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS calendar_event_links (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                sync_status TEXT NOT NULL,
                conflict_status TEXT NOT NULL,
                last_synced_at DATETIME,
                source_modified_at DATETIME,
                tombstoned_at DATETIME
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_policy (
                id TEXT PRIMARY KEY,
                permission_status TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS mutation_batches (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                requires_confirmation INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS mutation_records (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                target_table TEXT NOT NULL,
                target_id TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
            """,
        ]
        for statement in statements:
            conn.execute(statement)

    def _migrate_legacy_items_to_native_workflow(self, conn: sqlite3.Connection) -> None:
        """Promote legacy item rows into normalized native workflow tables."""
        rows = conn.execute(
            """
            SELECT id, type, title, status, parent_id, created_at, updated_at, original_ek_id
            FROM items
            """
        ).fetchall()

        for item_id, item_type, title, status, parent_id, created_at, updated_at, original_ek_id in rows:
            if item_type == "inbox":
                self._insert_native_capture_and_inbox_rows(
                    conn,
                    item_id=item_id,
                    title=title,
                    origin_type="reminders_import" if original_ek_id else "manual_capture",
                    source_ref=original_ek_id or None,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            elif item_type == "project":
                self._insert_native_project_row(
                    conn,
                    project_id=item_id,
                    name=title,
                    status=status,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            elif item_type == "action":
                self._insert_native_task_row(
                    conn,
                    task_id=item_id,
                    title=title,
                    status=status,
                    project_id=parent_id,
                    created_at=created_at,
                    updated_at=updated_at,
                )

    def _insert_native_capture_and_inbox_rows(
        self,
        conn: sqlite3.Connection,
        *,
        item_id: str,
        title: str,
        origin_type: str,
        source_ref: str | None,
        created_at: str | None,
        updated_at: str | None,
    ) -> None:
        created_value = created_at or _iso(datetime.now(timezone.utc))
        updated_value = updated_at or created_value
        conn.execute(
            """
            INSERT OR IGNORE INTO raw_captures (id, source, raw_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, origin_type, title, created_value),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO inbox_items (
                id, raw_capture_id, origin_type, inbox_state, source_ref,
                imported_at, task_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                item_id,
                item_id,
                origin_type,
                "needs_clarification",
                source_ref,
                created_value if source_ref else None,
                created_value,
                updated_value,
            ),
        )

    def _insert_native_project_row(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        name: str,
        status: str,
        created_at: str | None,
        updated_at: str | None,
    ) -> None:
        created_value = created_at or _iso(datetime.now(timezone.utc))
        updated_value = updated_at or created_value
        conn.execute(
            """
            INSERT OR IGNORE INTO projects (id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, status, created_value, updated_value),
        )

    def _insert_native_task_row(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        title: str,
        status: str,
        project_id: str | None,
        created_at: str | None,
        updated_at: str | None,
    ) -> None:
        created_value = created_at or _iso(datetime.now(timezone.utc))
        updated_value = updated_at or created_value
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks (
                id, title, status, project_id, time_sensitivity, effort_band, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, title, status, project_id, "none", "medium", created_value, updated_value),
        )

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
            self._insert_native_capture_and_inbox_rows(
                conn,
                item_id=item.id,
                title=item.title,
                origin_type="reminders_import" if item.original_ek_id else "manual_capture",
                source_ref=item.original_ek_id,
                created_at=_iso(item.created_at),
                updated_at=_iso(item.updated_at),
            )
            conn.commit()

    def clarify_inbox_item(
        self,
        *,
        inbox_item_id: str,
        clarified_title: str,
        destination_type: Literal["task", "project"],
        project_title: str | None,
    ) -> None:
        """Convert a raw inbox capture into a structured task or project."""
        now = _iso(datetime.now(timezone.utc))
        if now is None:
            raise RuntimeError("Expected clarify timestamp to be available.")

        with sqlite3.connect(self._path) as conn:
            item_row = conn.execute(
                "SELECT created_at FROM items WHERE id = ?",
                (inbox_item_id,),
            ).fetchone()
            if item_row is None:
                raise ValueError(f"Unknown inbox item: {inbox_item_id}")
            created_at = item_row[0] or now

            batch_id = self._insert_mutation_batch(
                conn,
                source="capture_clarify",
                requires_confirmation=False,
                created_at=now,
            )

            if destination_type == "task":
                project_id = self._find_or_create_project(
                    conn,
                    title=project_title,
                    created_at=now,
                    batch_id=batch_id,
                )
                conn.execute(
                    """
                    UPDATE items
                    SET type = 'action', title = ?, parent_id = ?, status = 'active', updated_at = ?
                    WHERE id = ?
                    """,
                    (clarified_title, project_id, now, inbox_item_id),
                )
                conn.execute(
                    """
                    INSERT INTO tasks (
                        id, title, status, project_id, source_inbox_item_id,
                        time_sensitivity, effort_band, created_at, updated_at
                    )
                    VALUES (?, ?, 'active', ?, ?, 'none', 'medium', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        status = excluded.status,
                        project_id = excluded.project_id,
                        source_inbox_item_id = excluded.source_inbox_item_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        inbox_item_id,
                        clarified_title,
                        project_id,
                        inbox_item_id,
                        created_at,
                        now,
                    ),
                )
                conn.execute(
                    """
                    UPDATE inbox_items
                    SET inbox_state = 'clarified',
                        task_id = ?,
                        clarified_task_id = ?,
                        clarified_project_id = ?,
                        clarified_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (inbox_item_id, inbox_item_id, project_id, now, now, inbox_item_id),
                )
                self._insert_mutation_record(
                    conn,
                    batch_id=batch_id,
                    target_table="tasks",
                    target_id=inbox_item_id,
                    action="clarify_accept",
                    payload={
                        "destination_type": "task",
                        "project_id": project_id,
                        "title": clarified_title,
                    },
                    created_at=now,
                )
            else:
                conn.execute(
                    """
                    UPDATE items
                    SET type = 'project', title = ?, parent_id = NULL, status = 'active', updated_at = ?
                    WHERE id = ?
                    """,
                    (clarified_title, now, inbox_item_id),
                )
                conn.execute("DELETE FROM tasks WHERE id = ?", (inbox_item_id,))
                conn.execute(
                    """
                    INSERT INTO projects (id, name, status, created_at, updated_at)
                    VALUES (?, ?, 'active', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (inbox_item_id, clarified_title, created_at, now),
                )
                conn.execute(
                    """
                    UPDATE inbox_items
                    SET inbox_state = 'converted_to_project',
                        task_id = NULL,
                        clarified_task_id = NULL,
                        clarified_project_id = ?,
                        clarified_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (inbox_item_id, now, now, inbox_item_id),
                )
                self._insert_mutation_record(
                    conn,
                    batch_id=batch_id,
                    target_table="projects",
                    target_id=inbox_item_id,
                    action="clarify_accept",
                    payload={
                        "destination_type": "project",
                        "title": clarified_title,
                    },
                    created_at=now,
                )

            conn.commit()

    def reject_inbox_item(self, inbox_item_id: str) -> None:
        """Archive an inbox capture while preserving raw capture history."""
        now = _iso(datetime.now(timezone.utc))
        if now is None:
            raise RuntimeError("Expected reject timestamp to be available.")

        with sqlite3.connect(self._path) as conn:
            batch_id = self._insert_mutation_batch(
                conn,
                source="capture_clarify",
                requires_confirmation=False,
                created_at=now,
            )
            conn.execute(
                "UPDATE items SET status = 'archived', updated_at = ? WHERE id = ?",
                (now, inbox_item_id),
            )
            conn.execute(
                """
                UPDATE inbox_items
                SET inbox_state = 'rejected',
                    clarified_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, inbox_item_id),
            )
            self._insert_mutation_record(
                conn,
                batch_id=batch_id,
                target_table="inbox_items",
                target_id=inbox_item_id,
                action="clarify_reject",
                payload={"inbox_item_id": inbox_item_id},
                created_at=now,
            )
            conn.commit()

    def _find_or_create_project(
        self,
        conn: sqlite3.Connection,
        *,
        title: str | None,
        created_at: str,
        batch_id: str,
    ) -> str | None:
        normalized = (title or "").strip()
        if not normalized:
            return None

        row = conn.execute(
            """
            SELECT id
            FROM projects
            WHERE lower(name) = lower(?) AND status != 'archived'
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        if row is not None:
            return str(row[0])

        project_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            )
            VALUES (?, 'project', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
            """,
            (project_id, normalized, created_at, created_at),
        )
        conn.execute(
            """
            INSERT INTO projects (id, name, status, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?)
            """,
            (project_id, normalized, created_at, created_at),
        )
        self._insert_mutation_record(
            conn,
            batch_id=batch_id,
            target_table="projects",
            target_id=project_id,
            action="create",
            payload={"title": normalized},
            created_at=created_at,
        )
        return project_id

    def _insert_mutation_batch(
        self,
        conn: sqlite3.Connection,
        *,
        source: str,
        requires_confirmation: bool,
        created_at: str,
    ) -> str:
        batch_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO mutation_batches (id, source, requires_confirmation, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (batch_id, source, int(requires_confirmation), created_at),
        )
        return batch_id

    def _insert_mutation_record(
        self,
        conn: sqlite3.Connection,
        *,
        batch_id: str,
        target_table: str,
        target_id: str,
        action: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO mutation_records (
                id, batch_id, target_table, target_id, action, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                batch_id,
                target_table,
                target_id,
                action,
                json.dumps(payload, sort_keys=True),
                created_at,
            ),
        )

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
        """Return active items filtered by estimated_duration range."""
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

    def replace_daily_plan(
        self, plan_date: str, entries: list[DailyPlanEntryInput]
    ) -> None:
        """Replace all daily-plan entries for a specific date."""
        now = _iso(datetime.now(timezone.utc))
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "DELETE FROM daily_plan_entries WHERE plan_date = ?",
                (plan_date,),
            )
            for entry in entries:
                conn.execute(
                    """
                    INSERT INTO daily_plan_entries (
                        plan_date, item_id, bucket, position, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        plan_date,
                        entry["item_id"],
                        entry["bucket"],
                        entry["position"],
                        now,
                    ),
                )
            conn.commit()

    def list_daily_plan(self, plan_date: str) -> list[DailyPlanEntryRecord]:
        """Return plan entries for a date ordered by bucket then position."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT d.bucket, d.position, i.*
                FROM daily_plan_entries d
                JOIN items i ON i.id = d.item_id
                WHERE d.plan_date = ?
                ORDER BY
                    CASE d.bucket WHEN 'top' THEN 0 ELSE 1 END,
                    d.position ASC
                """,
                (plan_date,),
            ).fetchall()
        return [
            {
                "item": _row_to_item(row),
                "bucket": row["bucket"],
                "position": row["position"],
            }
            for row in rows
        ]

    def get_daily_plan_summary(self, plan_date: str) -> dict[str, int]:
        """Return completion totals for top and bonus planned items."""
        summary = {
            "top_total": 0,
            "top_completed": 0,
            "bonus_total": 0,
            "bonus_completed": 0,
        }
        for entry in self.list_daily_plan(plan_date):
            bucket = entry["bucket"]
            total_key = f"{bucket}_total"
            completed_key = f"{bucket}_completed"
            summary[total_key] += 1
            if entry["item"].status == "done":
                summary[completed_key] += 1
        return summary

    def mark_daily_plan_recapped(self, plan_date: str) -> None:
        """Persist that the user explicitly completed recap for a plan date."""
        wrapped_at = _iso(datetime.now(timezone.utc))
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO daily_wrap_status (plan_date, wrapped_at)
                VALUES (?, ?)
                ON CONFLICT(plan_date) DO UPDATE SET wrapped_at = excluded.wrapped_at
                """,
                (plan_date, wrapped_at),
            )
            conn.commit()

    def get_latest_unrecapped_plan_date(self, before_date: str) -> Optional[str]:
        """Return the latest prior plan date that has not been explicitly recapped."""
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                """
                SELECT DISTINCT d.plan_date
                FROM daily_plan_entries d
                LEFT JOIN daily_wrap_status w ON w.plan_date = d.plan_date
                WHERE d.plan_date < ? AND w.plan_date IS NULL
                ORDER BY d.plan_date DESC
                LIMIT 1
                """,
                (before_date,),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

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

    def create_assistant_turn(self, turn: AssistantTurn) -> None:
        """Persist an assistant turn."""
        if turn.proposal is not None:
            raw_contract = turn.proposal.payload.get("agent_contract")
            if raw_contract is None:
                raise ValueError("Assistant proposals must include agent_contract")
            AssistantAgentContract.model_validate(raw_contract)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO assistant_turns (
                    id, prompt, response, route, proposal_json, proposal_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.id,
                    turn.prompt,
                    turn.response,
                    turn.route,
                    json.dumps(turn.proposal.model_dump() if turn.proposal else None),
                    turn.proposal_status,
                    _iso(turn.created_at),
                    _iso(turn.updated_at),
                ),
            )
            conn.commit()

    def get_assistant_turn(self, turn_id: str) -> AssistantTurn | None:
        """Return one assistant turn by id."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM assistant_turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
        if row is None:
            return None
        turn = _row_to_assistant_turn(row)
        return turn.model_copy(update={"audit_steps": self.list_assistant_audit_steps(turn_id)})

    def list_assistant_turns(self, limit: int = 30) -> list[AssistantTurn]:
        """Return assistant turns ordered newest-first."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM assistant_turns ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        turns = [_row_to_assistant_turn(row) for row in rows]
        return [
            turn.model_copy(update={"audit_steps": self.list_assistant_audit_steps(turn.id)})
            for turn in turns
        ]

    def update_assistant_proposal_status(self, turn_id: str, status: str) -> None:
        """Persist proposal-status updates for an assistant turn."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE assistant_turns
                SET proposal_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, _iso(datetime.now(timezone.utc)), turn_id),
            )
            conn.commit()

    def create_assistant_audit_steps(
        self, turn_id: str, steps: list[AssistantAuditStep]
    ) -> None:
        """Persist audit steps for an assistant turn."""
        if not steps:
            return
        with sqlite3.connect(self._path) as conn:
            for step in steps:
                conn.execute(
                    """
                    INSERT INTO assistant_audit_steps (
                        id, turn_id, stage, status, summary, payload_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        turn_id,
                        step.stage,
                        step.status,
                        step.summary,
                        json.dumps(step.payload),
                        _iso(step.created_at),
                    ),
                )
            conn.commit()

    def list_assistant_audit_steps(self, turn_id: str) -> list[AssistantAuditStep]:
        """Return audit steps for a persisted assistant turn."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT stage, status, summary, payload_json, created_at
                FROM assistant_audit_steps
                WHERE turn_id = ?
                ORDER BY created_at ASC
                """,
                (turn_id,),
            ).fetchall()
        return [_row_to_assistant_audit_step(row) for row in rows]

    def insert_memory_entry(self, entry: MemoryEntry) -> None:
        """Persist a memory entry."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO memory_entries (
                    id, kind, scope, scope_ref, value, source, confidence, enabled,
                    created_at, updated_at, last_confirmed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.kind,
                    entry.scope,
                    entry.scope_ref,
                    entry.value,
                    entry.source,
                    entry.confidence,
                    int(entry.enabled),
                    _iso(entry.created_at),
                    _iso(entry.updated_at),
                    _iso(entry.last_confirmed_at),
                ),
            )
            conn.commit()

    def get_memory_entry(self, memory_id: str) -> MemoryEntry | None:
        """Return one memory entry by id."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM memory_entries WHERE id = ?",
                (memory_id,),
            ).fetchone()
        return _row_to_memory_entry(row) if row else None

    def list_memory_entries(
        self,
        *,
        query: str | None = None,
        include_disabled: bool = True,
    ) -> list[MemoryEntry]:
        """Return memory entries ordered by freshness."""
        sql = "SELECT * FROM memory_entries"
        params: list[Any] = []
        clauses: list[str] = []
        if not include_disabled:
            clauses.append("enabled = 1")
        if query:
            clauses.append("LOWER(value) LIKE ?")
            params.append(f"%{query.lower()}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC, created_at DESC"

        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_memory_entry(row) for row in rows]

    def update_memory_entry(self, entry: MemoryEntry) -> None:
        """Update an existing memory entry."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE memory_entries
                SET kind = ?, scope = ?, scope_ref = ?, value = ?, source = ?,
                    confidence = ?, enabled = ?, updated_at = ?, last_confirmed_at = ?
                WHERE id = ?
                """,
                (
                    entry.kind,
                    entry.scope,
                    entry.scope_ref,
                    entry.value,
                    entry.source,
                    entry.confidence,
                    int(entry.enabled),
                    _iso(entry.updated_at),
                    _iso(entry.last_confirmed_at),
                    entry.id,
                ),
            )
            conn.commit()

    def delete_memory_entry(self, memory_id: str) -> None:
        """Delete a persisted memory entry."""
        with sqlite3.connect(self._path) as conn:
            conn.execute("DELETE FROM memory_entries WHERE id = ?", (memory_id,))
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


def _json_loads(raw: str | None, default: Any) -> Any:
    """Load JSON with a default fallback."""
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _row_to_assistant_turn(row: sqlite3.Row) -> AssistantTurn:
    """Convert database row to AssistantTurn."""
    proposal_raw = _json_loads(row["proposal_json"], None)
    proposal = AssistantProposal(**proposal_raw) if proposal_raw else None
    return AssistantTurn(
        id=row["id"],
        prompt=row["prompt"],
        response=row["response"],
        route=row["route"],
        proposal=proposal,
        proposal_status=row["proposal_status"],
        audit_steps=[],
        created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
        updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
    )


def _row_to_assistant_audit_step(row: sqlite3.Row) -> AssistantAuditStep:
    """Convert database row to AssistantAuditStep."""
    return AssistantAuditStep(
        stage=row["stage"],
        status=row["status"],
        summary=row["summary"],
        payload=_json_loads(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
    )


def _row_to_memory_entry(row: sqlite3.Row) -> MemoryEntry:
    """Convert database row to MemoryEntry."""
    return MemoryEntry(
        id=row["id"],
        kind=row["kind"],
        scope=row["scope"],
        scope_ref=row["scope_ref"],
        value=row["value"],
        source=row["source"],
        confidence=float(row["confidence"]),
        enabled=bool(row["enabled"]),
        created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
        updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
        last_confirmed_at=_parse_dt(row["last_confirmed_at"]),
    )
