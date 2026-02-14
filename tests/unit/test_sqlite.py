"""Unit tests for SQLite layer."""

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
