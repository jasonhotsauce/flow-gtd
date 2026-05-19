"""Regression tests for Apple Reminders sync behavior."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from typing import Any

from flow.database.sqlite import SqliteDB
from flow.models import Item
from flow.sync import reminders


class _FakeReminder:
    def __init__(
        self,
        *,
        ek_id: str,
        title: str,
        completed: bool,
        calendar_title: str = "Default",
        modified_at: str = "2026-04-20T10:00:00+00:00",
    ) -> None:
        self._ek_id = ek_id
        self._title = title
        self._completed = completed
        self._calendar = SimpleNamespace(title=lambda: calendar_title)
        self._modified_at = modified_at

    def isCompleted(self) -> bool:
        return self._completed

    def calendarItemIdentifier(self) -> str:
        return self._ek_id

    def title(self) -> str:
        return self._title

    def setTitle_(self, title: str) -> None:
        self._title = title

    def setCompleted_(self, completed: bool) -> None:
        self._completed = completed

    def calendar(self) -> SimpleNamespace:
        return self._calendar

    def lastModifiedDate(self) -> str:
        return self._modified_at


class _FakeStore:
    def __init__(self, reminder_list: list[_FakeReminder]) -> None:
        self._reminder_list = reminder_list
        self.saved_reminders: list[_FakeReminder] = []

    def init(self) -> _FakeStore:
        return self

    def requestFullAccessToRemindersWithCompletion_(self, completion: Any) -> None:
        completion(True, None)

    def calendarsForEntityType_(self, _entity_type: int) -> list[str]:
        return ["Default"]

    def predicateForRemindersInCalendars_(self, calendars: list[str]) -> list[str]:
        return calendars

    def fetchRemindersMatchingPredicate_completion_(
        self, _predicate: object, completion: Any
    ) -> None:
        completion(self._reminder_list)

    def calendarItemWithIdentifier_(self, external_id: str) -> _FakeReminder | None:
        for reminder in self._reminder_list:
            if reminder.calendarItemIdentifier() == external_id:
                return reminder
        return None

    def saveReminder_commit_error_(
        self, reminder: _FakeReminder, _commit: bool, _error: object
    ) -> bool:
        self.saved_reminders.append(reminder)
        return True


def test_sync_archives_previously_imported_items_when_source_reminder_is_completed(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Completed reminders should no longer remain active in Flow after re-sync."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="flow-1",
            type="inbox",
            title="Pay rent",
            status="active",
            original_ek_id="ek-1",
        )
    )

    fake_store = _FakeStore(
        [_FakeReminder(ek_id="ek-1", title="Pay rent", completed=True)]
    )
    fake_eventkit = SimpleNamespace(
        EKEventStore=SimpleNamespace(
            authorizationStatusForEntityType_=staticmethod(
                lambda _entity_type: reminders._EK_AUTH_FULL_ACCESS
            ),
            alloc=lambda: fake_store,
        )
    )

    monkeypatch.setattr(reminders, "EventKit", fake_eventkit)
    monkeypatch.setattr(reminders, "_reminders_available", lambda: True)

    count, message = reminders.sync_reminders_to_flow(temp_db_path)

    synced_item = db.get_item("flow-1")

    assert count == 0
    assert message == "Imported 0 incomplete reminders."
    assert synced_item is not None
    assert synced_item.status == "archived"


def test_sync_skips_incomplete_reminders_in_recently_deleted_calendar(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Recently Deleted reminders should never be imported into Flow."""
    fake_store = _FakeStore(
        [
            _FakeReminder(
                ek_id="ek-deleted",
                title="Do not import me",
                completed=False,
                calendar_title="Recently Deleted",
            )
        ]
    )
    fake_eventkit = SimpleNamespace(
        EKEventStore=SimpleNamespace(
            authorizationStatusForEntityType_=staticmethod(
                lambda _entity_type: reminders._EK_AUTH_FULL_ACCESS
            ),
            alloc=lambda: fake_store,
        )
    )

    monkeypatch.setattr(reminders, "EventKit", fake_eventkit)
    monkeypatch.setattr(reminders, "_reminders_available", lambda: True)

    count, message = reminders.sync_reminders_to_flow(temp_db_path)

    db = SqliteDB(temp_db_path)
    synced_item = db.get_item_by_ek_id("ek-deleted")

    assert count == 0
    assert message == "Imported 0 incomplete reminders."
    assert synced_item is None


def test_sync_flow_to_reminders_requires_explicit_write_back(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Flow must not write back to Apple Reminders unless explicitly requested."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="flow-1",
            type="action",
            title="Updated local title",
            status="active",
            original_ek_id="ek-1",
        )
    )
    _insert_reminder_link(temp_db_path, task_id="flow-1", external_id="ek-1")
    fake_store = _FakeStore(
        [_FakeReminder(ek_id="ek-1", title="Original reminder", completed=False)]
    )
    _patch_eventkit(monkeypatch, fake_store)

    count, message = reminders.sync_flow_to_reminders(temp_db_path)

    assert count == 0
    assert "Write-back disabled" in message
    assert fake_store.saved_reminders == []


def test_sync_flow_to_reminders_writes_linked_local_changes_when_enabled(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Explicit write-back should update linked reminders and refresh sync metadata."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="flow-1",
            type="action",
            title="Updated local title",
            status="done",
            original_ek_id="ek-1",
        )
    )
    _insert_reminder_link(temp_db_path, task_id="flow-1", external_id="ek-1")
    fake_reminder = _FakeReminder(ek_id="ek-1", title="Original reminder", completed=False)
    fake_store = _FakeStore([fake_reminder])
    _patch_eventkit(monkeypatch, fake_store)

    count, message = reminders.sync_flow_to_reminders(temp_db_path, write_back=True)

    assert count == 1
    assert message == "Wrote 1 Flow change to Apple Reminders."
    assert fake_reminder.title() == "Updated local title"
    assert fake_reminder.isCompleted() is True
    assert fake_store.saved_reminders == [fake_reminder]
    link = _fetch_reminder_link(temp_db_path, "flow-1")
    assert link["sync_status"] == "synced"
    assert link["conflict_status"] == "none"


def test_sync_flow_to_reminders_marks_source_changed_conflict_without_writing(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Changed source reminders should become explicit conflicts instead of being overwritten."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="flow-1",
            type="action",
            title="Local edit",
            status="active",
            original_ek_id="ek-1",
        )
    )
    _insert_reminder_link(
        temp_db_path,
        task_id="flow-1",
        external_id="ek-1",
        source_modified_at="2026-04-20T10:00:00+00:00",
    )
    fake_store = _FakeStore(
        [
            _FakeReminder(
                ek_id="ek-1",
                title="Reminder-side edit",
                completed=False,
                modified_at="2026-04-20T11:00:00+00:00",
            )
        ]
    )
    _patch_eventkit(monkeypatch, fake_store)

    count, message = reminders.sync_flow_to_reminders(temp_db_path, write_back=True)

    assert count == 0
    assert "1 conflict" in message
    assert fake_store.saved_reminders == []
    link = _fetch_reminder_link(temp_db_path, "flow-1")
    assert link["sync_status"] == "conflict"
    assert link["conflict_status"] == "source_changed"


def test_sync_flow_to_reminders_skips_already_synced_links(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    """Write-back should be idempotent when Flow has no newer local changes."""
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="flow-1",
            type="action",
            title="Already synced",
            status="active",
            original_ek_id="ek-1",
        )
    )
    _insert_reminder_link(
        temp_db_path,
        task_id="flow-1",
        external_id="ek-1",
        last_synced_at="2099-04-20T10:00:00+00:00",
    )
    fake_store = _FakeStore(
        [_FakeReminder(ek_id="ek-1", title="Already synced", completed=False)]
    )
    _patch_eventkit(monkeypatch, fake_store)

    count, message = reminders.sync_flow_to_reminders(temp_db_path, write_back=True)

    assert count == 0
    assert message == "Wrote 0 Flow changes to Apple Reminders."
    assert fake_store.saved_reminders == []


def _patch_eventkit(monkeypatch: Any, fake_store: _FakeStore) -> None:
    fake_eventkit = SimpleNamespace(
        EKEventStore=SimpleNamespace(
            authorizationStatusForEntityType_=staticmethod(
                lambda _entity_type: reminders._EK_AUTH_FULL_ACCESS
            ),
            alloc=lambda: fake_store,
        )
    )
    monkeypatch.setattr(reminders, "EventKit", fake_eventkit)
    monkeypatch.setattr(reminders, "_reminders_available", lambda: True)


def _insert_reminder_link(
    db_path: Any,
    *,
    task_id: str,
    external_id: str,
    source_modified_at: str = "2026-04-20T10:00:00+00:00",
    last_synced_at: str = "2000-04-20T10:00:00+00:00",
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reminder_links (
                id, task_id, external_id, sync_status, conflict_status,
                last_synced_at, source_modified_at, tombstoned_at
            ) VALUES (?, ?, ?, 'linked', 'none', ?, ?, NULL)
            """,
            (
                f"link-{task_id}",
                task_id,
                external_id,
                last_synced_at,
                source_modified_at,
            ),
        )


def _fetch_reminder_link(db_path: Any, task_id: str) -> Any:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = None
        row = conn.execute(
            """
            SELECT sync_status, conflict_status
            FROM reminder_links
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    return {"sync_status": row[0], "conflict_status": row[1]}
