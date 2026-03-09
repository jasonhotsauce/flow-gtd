"""Unit tests for SQLite layer."""

from datetime import datetime, timedelta, timezone

from flow.database.sqlite import SqliteDB
from flow.models import Item


def test_init_db(db: SqliteDB) -> None:
    """init_db creates table and indexes."""
    db.init_db()
    # No exception; table exists (insert will work)
    item = Item(id="x", type="inbox", title="t", status="active")
    db.insert_inbox(item)
    rows = db.list_inbox()
    assert len(rows) == 1
    assert rows[0].title == "t"


def test_insert_and_list_inbox(db: SqliteDB, sample_item: Item) -> None:
    """insert_inbox and list_inbox roundtrip."""
    db.insert_inbox(sample_item)
    items = db.list_inbox()
    assert len(items) == 1
    assert items[0].id == sample_item.id
    assert items[0].title == sample_item.title


def test_get_item(db: SqliteDB, sample_item: Item) -> None:
    """get_item returns item by id."""
    db.insert_inbox(sample_item)
    got = db.get_item(sample_item.id)
    assert got is not None
    assert got.id == sample_item.id
    got_missing = db.get_item("nonexistent")
    assert got_missing is None


def test_update_item(db: SqliteDB, sample_item: Item) -> None:
    """update_item persists changes."""
    db.insert_inbox(sample_item)
    updated = sample_item.model_copy(update={"title": "Updated title"})
    db.update_item(updated)
    got = db.get_item(sample_item.id)
    assert got is not None
    assert got.title == "Updated title"


def test_list_actions(db: SqliteDB) -> None:
    """list_actions filters by status."""
    db.insert_inbox(Item(id="a", type="inbox", title="A", status="active"))
    db.insert_inbox(Item(id="b", type="action", title="B", status="done"))
    active = db.list_actions(status="active")
    assert len(active) >= 1
    done = db.list_actions(status="done")
    assert len(done) >= 1


def test_list_inbox_excludes_done_and_archived(db: SqliteDB) -> None:
    """list_inbox returns only open inbox items (excludes done and archived)."""
    db.insert_inbox(Item(id="open", type="inbox", title="Open", status="active"))
    db.insert_inbox(Item(id="completed", type="inbox", title="Done", status="active"))
    db.insert_inbox(Item(id="archived", type="inbox", title="Archived", status="active"))

    items = db.list_inbox()
    assert len(items) == 3

    db.update_item(Item(id="completed", type="inbox", title="Done", status="done"))
    db.update_item(Item(id="archived", type="inbox", title="Archived", status="archived"))

    items = db.list_inbox()
    assert len(items) == 1
    assert items[0].id == "open"
    assert items[0].title == "Open"


def test_list_inbox_excludes_deferred_and_project_assigned_items(db: SqliteDB) -> None:
    """list_inbox returns only active, ungrouped inbox tasks."""
    db.insert_inbox(Item(id="visible", type="inbox", title="Visible", status="active"))
    db.insert_inbox(
        Item(id="waiting", type="inbox", title="Waiting", status="waiting")
    )
    db.insert_inbox(
        Item(id="someday", type="inbox", title="Someday", status="someday")
    )
    db.insert_inbox(
        Item(
            id="in_project",
            type="inbox",
            title="In project",
            status="active",
            parent_id="project-1",
        )
    )

    items = db.list_inbox()
    assert len(items) == 1
    assert items[0].id == "visible"


def test_list_stale_excludes_completed_items(db: SqliteDB) -> None:
    """list_stale should not include done items in weekly review stale list."""
    old = datetime.now(timezone.utc) - timedelta(days=30)

    db.insert_inbox(
        Item(
            id="stale-open",
            type="inbox",
            title="Stale open",
            status="active",
            created_at=old,
        )
    )
    db.insert_inbox(
        Item(
            id="stale-done",
            type="inbox",
            title="Stale done",
            status="done",
            created_at=old,
        )
    )

    stale_items = db.list_stale(days=14)
    stale_ids = {item.id for item in stale_items}

    assert "stale-open" in stale_ids
    assert "stale-done" not in stale_ids


def test_index_job_roundtrip(db: SqliteDB) -> None:
    """Index jobs should be persisted and status updates should be queryable."""
    db.enqueue_index_job(
        resource_id="r1",
        content_type="text",
        source="hello world",
        title="Hello",
        summary="hello summary",
    )

    jobs = db.list_index_jobs(status="pending", limit=10)
    assert len(jobs) == 1
    assert jobs[0]["resource_id"] == "r1"

    db.update_index_job_status(job_id=jobs[0]["id"], status="done")
    done_jobs = db.list_index_jobs(status="done", limit=10)
    assert len(done_jobs) == 1
    assert done_jobs[0]["resource_id"] == "r1"


def test_replace_and_list_daily_plan_orders_top_then_bonus(db: SqliteDB) -> None:
    """Daily plan entries should round-trip in bucket/position order."""
    for item_id in ("task-1", "task-2", "task-3"):
        db.insert_inbox(Item(id=item_id, type="action", title=item_id, status="active"))

    db.replace_daily_plan(
        plan_date="2026-03-08",
        entries=[
            {"item_id": "task-2", "bucket": "bonus", "position": 1},
            {"item_id": "task-1", "bucket": "top", "position": 2},
            {"item_id": "task-3", "bucket": "top", "position": 1},
        ],
    )

    entries = db.list_daily_plan("2026-03-08")

    assert [(entry["bucket"], entry["position"], entry["item"].id) for entry in entries] == [
        ("top", 1, "task-3"),
        ("top", 2, "task-1"),
        ("bonus", 1, "task-2"),
    ]


def test_replace_daily_plan_overwrites_existing_entries_for_date(db: SqliteDB) -> None:
    """Replacing a plan should clear older entries for the same date first."""
    for item_id in ("task-1", "task-2", "task-3"):
        db.insert_inbox(Item(id=item_id, type="action", title=item_id, status="active"))

    db.replace_daily_plan(
        plan_date="2026-03-08",
        entries=[
            {"item_id": "task-1", "bucket": "top", "position": 1},
            {"item_id": "task-2", "bucket": "bonus", "position": 1},
        ],
    )
    db.replace_daily_plan(
        plan_date="2026-03-08",
        entries=[
            {"item_id": "task-3", "bucket": "top", "position": 1},
        ],
    )

    entries = db.list_daily_plan("2026-03-08")

    assert len(entries) == 1
    assert entries[0]["item"].id == "task-3"


def test_get_daily_plan_summary_counts_done_and_open_items(db: SqliteDB) -> None:
    """Daily plan summary should separate completed and open top/bonus items."""
    db.insert_inbox(Item(id="top-done", type="action", title="Top done", status="done"))
    db.insert_inbox(Item(id="top-open", type="action", title="Top open", status="active"))
    db.insert_inbox(Item(id="bonus-done", type="action", title="Bonus done", status="done"))
    db.insert_inbox(Item(id="bonus-open", type="action", title="Bonus open", status="active"))

    db.replace_daily_plan(
        plan_date="2026-03-08",
        entries=[
            {"item_id": "top-done", "bucket": "top", "position": 1},
            {"item_id": "top-open", "bucket": "top", "position": 2},
            {"item_id": "bonus-done", "bucket": "bonus", "position": 1},
            {"item_id": "bonus-open", "bucket": "bonus", "position": 2},
        ],
    )

    summary = db.get_daily_plan_summary("2026-03-08")

    assert summary == {
        "top_total": 2,
        "top_completed": 1,
        "bonus_total": 2,
        "bonus_completed": 1,
    }
