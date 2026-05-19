"""Red-state tests for the planned native capture/clarify workflow."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flow.database.sqlite import SqliteDB
from flow.models import Item


def test_insert_inbox_keeps_raw_capture_pending_before_clarify(
    temp_db_path: Path,
) -> None:
    """Raw capture storage should exist before any structured clarify conversion."""
    db = SqliteDB(temp_db_path)
    db.init_db()

    db.insert_inbox(
        Item(
            id="capture-clarify-1",
            type="inbox",
            title="Call Alice about launch plan",
            status="active",
        )
    )

    with sqlite3.connect(temp_db_path) as conn:
        raw_capture = conn.execute(
            """
            SELECT source, raw_text
            FROM raw_captures
            WHERE id = 'capture-clarify-1'
            """
        ).fetchone()
        inbox_item = conn.execute(
            """
            SELECT raw_capture_id, inbox_state
            FROM inbox_items
            WHERE id = 'capture-clarify-1'
            """
        ).fetchone()
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    assert raw_capture == ("manual_capture", "Call Alice about launch plan")
    assert inbox_item == ("capture-clarify-1", "needs_clarification")
    assert task_count == 0
    assert project_count == 0


def test_inbox_items_schema_reserves_clarify_transition_fields(
    temp_db_path: Path,
) -> None:
    """Clarify should have explicit room to record task/project conversion outcomes."""
    db = SqliteDB(temp_db_path)
    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(inbox_items)").fetchall()
        }

    assert "clarified_task_id" in columns
    assert "clarified_project_id" in columns
    assert "clarified_at" in columns


def test_tasks_schema_links_structured_conversion_back_to_inbox_origin(
    temp_db_path: Path,
) -> None:
    """Structured task creation should keep an explicit link back to the inbox item."""
    db = SqliteDB(temp_db_path)
    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}

    assert "source_inbox_item_id" in columns


def test_clarify_inbox_item_can_promote_capture_into_task_and_project(
    temp_db_path: Path,
) -> None:
    """Clarify acceptance should convert a raw capture into structured task state."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="capture-task-1",
            type="inbox",
            title="Call Alice about launch plan",
            status="active",
        )
    )

    db.clarify_inbox_item(
        inbox_item_id="capture-task-1",
        clarified_title="Call Alice to confirm launch checklist",
        destination_type="task",
        project_title="Launch Prep",
    )

    with sqlite3.connect(temp_db_path) as conn:
        item_row = conn.execute(
            """
            SELECT type, title, parent_id, status
            FROM items
            WHERE id = 'capture-task-1'
            """
        ).fetchone()
        project_row = conn.execute(
            """
            SELECT name, status
            FROM projects
            WHERE id = (
                SELECT clarified_project_id
                FROM inbox_items
                WHERE id = 'capture-task-1'
            )
            """
        ).fetchone()
        workflow_row = conn.execute(
            """
            SELECT inbox_state, task_id, clarified_task_id, clarified_project_id
            FROM inbox_items
            WHERE id = 'capture-task-1'
            """
        ).fetchone()
        task_row = conn.execute(
            """
            SELECT title, project_id, source_inbox_item_id
            FROM tasks
            WHERE id = 'capture-task-1'
            """
        ).fetchone()
        mutation_row = conn.execute(
            """
            SELECT target_table, action
            FROM mutation_records
            WHERE batch_id = (
                SELECT id
                FROM mutation_batches
                ORDER BY created_at DESC
                LIMIT 1
            )
            ORDER BY target_table ASC
            """
        ).fetchall()

    assert item_row[0:2] == ("action", "Call Alice to confirm launch checklist")
    assert item_row[3] == "active"
    assert project_row == ("Launch Prep", "active")
    assert workflow_row[0] == "clarified"
    assert workflow_row[1] == "capture-task-1"
    assert workflow_row[2] == "capture-task-1"
    assert workflow_row[3]
    assert task_row[0] == "Call Alice to confirm launch checklist"
    assert task_row[2] == "capture-task-1"
    assert mutation_row == [("projects", "create"), ("tasks", "clarify_accept")]


def test_clarify_inbox_item_can_promote_capture_into_project(
    temp_db_path: Path,
) -> None:
    """Project-shaped captures should become project rows instead of tasks."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="capture-project-1",
            type="inbox",
            title="Plan the offsite",
            status="active",
        )
    )

    db.clarify_inbox_item(
        inbox_item_id="capture-project-1",
        clarified_title="Q3 Offsite",
        destination_type="project",
        project_title=None,
    )

    with sqlite3.connect(temp_db_path) as conn:
        item_row = conn.execute(
            "SELECT type, title, status FROM items WHERE id = 'capture-project-1'"
        ).fetchone()
        project_row = conn.execute(
            "SELECT name, status FROM projects WHERE id = 'capture-project-1'"
        ).fetchone()
        task_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE id = 'capture-project-1'"
        ).fetchone()[0]
        workflow_row = conn.execute(
            """
            SELECT inbox_state, task_id, clarified_task_id, clarified_project_id
            FROM inbox_items
            WHERE id = 'capture-project-1'
            """
        ).fetchone()

    assert item_row == ("project", "Q3 Offsite", "active")
    assert project_row == ("Q3 Offsite", "active")
    assert task_count == 0
    assert workflow_row == (
        "converted_to_project",
        None,
        None,
        "capture-project-1",
    )


def test_reject_inbox_item_archives_capture_and_records_mutation(
    temp_db_path: Path,
) -> None:
    """Rejecting a clarify proposal should remove it from the live inbox without deleting the capture history."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="capture-reject-1",
            type="inbox",
            title="Maybe someday idea",
            status="active",
        )
    )

    db.reject_inbox_item("capture-reject-1")

    with sqlite3.connect(temp_db_path) as conn:
        item_row = conn.execute(
            "SELECT type, status FROM items WHERE id = 'capture-reject-1'"
        ).fetchone()
        workflow_row = conn.execute(
            """
            SELECT inbox_state, clarified_at
            FROM inbox_items
            WHERE id = 'capture-reject-1'
            """
        ).fetchone()
        raw_capture_row = conn.execute(
            "SELECT raw_text FROM raw_captures WHERE id = 'capture-reject-1'"
        ).fetchone()
        mutation_row = conn.execute(
            """
            SELECT target_table, action
            FROM mutation_records
            WHERE batch_id = (
                SELECT id
                FROM mutation_batches
                ORDER BY created_at DESC
                LIMIT 1
            )
            """
        ).fetchone()

    assert item_row == ("inbox", "archived")
    assert workflow_row[0] == "rejected"
    assert workflow_row[1] is not None
    assert raw_capture_row == ("Maybe someday idea",)
    assert mutation_row == ("inbox_items", "clarify_reject")
