"""Regression tests for native workflow storage migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flow.database.sqlite import SqliteDB
from flow.models import Item


def test_sqlite_db_bootstraps_workflow_tables(temp_db_path: Path) -> None:
    """The database bootstrap should create the normalized workflow tables."""
    db = SqliteDB(temp_db_path)

    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    table_names = {row[0] for row in rows}

    assert "raw_captures" in table_names
    assert "inbox_items" in table_names
    assert "tasks" in table_names
    assert "projects" in table_names
    assert "reminder_links" in table_names
    assert "calendar_event_links" in table_names
    assert "notification_policy" in table_names


def test_sqlite_db_migrates_existing_items_rows_into_workflow_tables(
    temp_db_path: Path,
) -> None:
    """Existing loose-schema rows should be promotable into workflow tables on init."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE items (
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
                estimated_duration INTEGER,
                updated_at DATETIME
            )
            """
        )
        conn.execute(
            """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (
                'legacy-inbox-1', 'inbox', 'Legacy inbox item', 'active', '[]', NULL,
                '2026-04-19T10:00:00+00:00', NULL, '{}', NULL, NULL, '2026-04-19T10:00:00+00:00'
            )
            """
        )
        conn.commit()

    db = SqliteDB(temp_db_path)

    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        raw_capture_count = conn.execute("SELECT COUNT(*) FROM raw_captures").fetchone()[0]
        inbox_item_count = conn.execute("SELECT COUNT(*) FROM inbox_items").fetchone()[0]

    assert raw_capture_count >= 1
    assert inbox_item_count >= 1


def test_sqlite_db_migrates_reminder_backed_items_with_origin_metadata(
    temp_db_path: Path,
) -> None:
    """Legacy reminder-backed inbox rows should preserve imported origin metadata."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE items (
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
                estimated_duration INTEGER,
                updated_at DATETIME
            )
            """
        )
        conn.execute(
            """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (
                'legacy-reminder-1', 'inbox', 'Imported reminder', 'active', '[]', NULL,
                '2026-04-19T10:00:00+00:00', NULL, '{}', 'ek-123', NULL, '2026-04-19T11:00:00+00:00'
            )
            """
        )
        conn.commit()

    db = SqliteDB(temp_db_path)
    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        row = conn.execute(
            """
            SELECT origin_type, source_ref, imported_at, inbox_state
            FROM inbox_items
            WHERE id = 'legacy-reminder-1'
            """
        ).fetchone()

    assert row == (
        "reminders_import",
        "ek-123",
        "2026-04-19T10:00:00+00:00",
        "needs_clarification",
    )


def test_insert_inbox_populates_normalized_capture_and_inbox_tables(
    temp_db_path: Path,
) -> None:
    """Current write paths should dual-write into normalized workflow tables."""
    db = SqliteDB(temp_db_path)
    db.init_db()

    db.insert_inbox(
        Item(
            id="new-inbox-1",
            type="inbox",
            title="Normalize this write path",
            status="active",
        )
    )

    with sqlite3.connect(temp_db_path) as conn:
        raw_capture = conn.execute(
            "SELECT source, raw_text FROM raw_captures WHERE id = 'new-inbox-1'"
        ).fetchone()
        inbox_item = conn.execute(
            """
            SELECT raw_capture_id, origin_type, inbox_state
            FROM inbox_items
            WHERE id = 'new-inbox-1'
            """
        ).fetchone()

    assert raw_capture == ("manual_capture", "Normalize this write path")
    assert inbox_item == ("new-inbox-1", "manual_capture", "needs_clarification")


def test_sqlite_db_migrates_legacy_projects_and_actions_into_normalized_tables(
    temp_db_path: Path,
) -> None:
    """Legacy projects and their actions should populate normalized project/task tables."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE items (
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
                estimated_duration INTEGER,
                updated_at DATETIME
            )
            """
        )
        conn.execute(
            """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (
                'legacy-project-1', 'project', 'Legacy project', 'active', '[]', NULL,
                '2026-04-19T10:00:00+00:00', NULL, '{}', NULL, NULL, '2026-04-19T11:00:00+00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (
                'legacy-action-1', 'action', 'Legacy action', 'waiting', '[]', 'legacy-project-1',
                '2026-04-19T10:05:00+00:00', NULL, '{}', NULL, 30, '2026-04-19T11:05:00+00:00'
            )
            """
        )
        conn.commit()

    db = SqliteDB(temp_db_path)
    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        project_row = conn.execute(
            "SELECT name, status FROM projects WHERE id = 'legacy-project-1'"
        ).fetchone()
        task_row = conn.execute(
            """
            SELECT title, status, project_id, effort_band
            FROM tasks
            WHERE id = 'legacy-action-1'
            """
        ).fetchone()

    assert project_row == ("Legacy project", "active")
    assert task_row == ("Legacy action", "waiting", "legacy-project-1", "medium")
