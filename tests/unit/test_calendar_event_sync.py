"""Regression tests for Flow-owned Apple Calendar event sync."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from flow.database.sqlite import SqliteDB
from flow.models import Item
from flow.sync import calendar_events


class _FakeEvent:
    def __init__(
        self,
        *,
        event_id: str = "event-1",
        title: str = "",
        modified_at: str = "2026-04-20T10:00:00+00:00",
    ) -> None:
        self._event_id = event_id
        self._title = title
        self._start = None
        self._end = None
        self._calendar = None
        self._modified_at = modified_at

    def calendarItemIdentifier(self) -> str:
        return self._event_id

    def title(self) -> str:
        return self._title

    def setTitle_(self, title: str) -> None:
        self._title = title

    def setStartDate_(self, value: object) -> None:
        self._start = value

    def setEndDate_(self, value: object) -> None:
        self._end = value

    def setCalendar_(self, value: object) -> None:
        self._calendar = value

    def lastModifiedDate(self) -> str:
        return self._modified_at


class _FakeStore:
    def __init__(self, existing_events: list[_FakeEvent] | None = None) -> None:
        self.events = {event.calendarItemIdentifier(): event for event in existing_events or []}
        self.saved_events: list[_FakeEvent] = []
        self.calendar = object()

    def init(self) -> _FakeStore:
        return self

    def defaultCalendarForNewEvents(self) -> object:
        return self.calendar

    def calendarItemWithIdentifier_(self, external_id: str) -> _FakeEvent | None:
        return self.events.get(external_id)

    def saveEvent_span_commit_error_(
        self, event: _FakeEvent, _span: int, _commit: bool, _error: object
    ) -> bool:
        self.saved_events.append(event)
        self.events[event.calendarItemIdentifier()] = event
        return True


def test_calendar_sync_creates_events_for_eligible_tasks(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="task-1",
            type="action",
            title="Draft calendar sync notes",
            status="active",
            due_date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            estimated_duration=30,
        )
    )
    fake_store = _FakeStore()
    _patch_eventkit(monkeypatch, fake_store)

    count, message = calendar_events.sync_flow_tasks_to_calendar(temp_db_path)

    assert count == 1
    assert message == "Created or updated 1 Flow calendar event."
    assert fake_store.saved_events[0].title() == "Draft calendar sync notes"
    link = _fetch_calendar_link(temp_db_path, "task-1")
    assert link["sync_status"] == "synced"
    assert link["conflict_status"] == "none"


def test_calendar_sync_skips_ineligible_tasks(monkeypatch: Any, temp_db_path: Any) -> None:
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="task-1",
            type="action",
            title="Missing duration",
            status="active",
            due_date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            estimated_duration=None,
        )
    )
    fake_store = _FakeStore()
    _patch_eventkit(monkeypatch, fake_store)

    count, _message = calendar_events.sync_flow_tasks_to_calendar(temp_db_path)

    assert count == 0
    assert fake_store.saved_events == []


def test_calendar_sync_updates_linked_event_when_source_is_unchanged(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="task-1",
            type="action",
            title="Updated event title",
            status="active",
            due_date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            estimated_duration=45,
        )
    )
    _insert_calendar_link(temp_db_path, task_id="task-1", external_id="event-1")
    fake_event = _FakeEvent(event_id="event-1", title="Old event title")
    fake_store = _FakeStore([fake_event])
    _patch_eventkit(monkeypatch, fake_store)

    count, _message = calendar_events.sync_flow_tasks_to_calendar(temp_db_path)

    assert count == 1
    assert fake_event.title() == "Updated event title"
    assert fake_store.saved_events == [fake_event]


def test_calendar_sync_marks_source_changed_conflict_without_overwriting(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="task-1",
            type="action",
            title="Local calendar edit",
            status="active",
            due_date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            estimated_duration=30,
        )
    )
    _insert_calendar_link(
        temp_db_path,
        task_id="task-1",
        external_id="event-1",
        source_modified_at="2026-04-20T10:00:00+00:00",
    )
    fake_event = _FakeEvent(
        event_id="event-1",
        title="Calendar-side edit",
        modified_at="2026-04-20T11:00:00+00:00",
    )
    fake_store = _FakeStore([fake_event])
    _patch_eventkit(monkeypatch, fake_store)

    count, message = calendar_events.sync_flow_tasks_to_calendar(temp_db_path)

    assert count == 0
    assert "1 conflict" in message
    assert fake_event.title() == "Calendar-side edit"
    assert fake_store.saved_events == []
    link = _fetch_calendar_link(temp_db_path, "task-1")
    assert link["sync_status"] == "conflict"
    assert link["conflict_status"] == "source_changed"


def test_calendar_sync_skips_already_synced_links(
    monkeypatch: Any, temp_db_path: Any
) -> None:
    db = SqliteDB(temp_db_path)
    db.init_db()
    db.insert_inbox(
        Item(
            id="task-1",
            type="action",
            title="Already synced event",
            status="active",
            due_date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            estimated_duration=30,
        )
    )
    _insert_calendar_link(
        temp_db_path,
        task_id="task-1",
        external_id="event-1",
        last_synced_at="2099-04-20T10:00:00+00:00",
    )
    fake_event = _FakeEvent(event_id="event-1", title="Already synced event")
    fake_store = _FakeStore([fake_event])
    _patch_eventkit(monkeypatch, fake_store)

    count, message = calendar_events.sync_flow_tasks_to_calendar(temp_db_path)

    assert count == 0
    assert message == "Created or updated 0 Flow calendar events."
    assert fake_store.saved_events == []


def _patch_eventkit(monkeypatch: Any, fake_store: _FakeStore) -> None:
    fake_eventkit = SimpleNamespace(
        EKEvent=SimpleNamespace(eventWithEventStore_=staticmethod(lambda _store: _FakeEvent())),
        EKEventStore=SimpleNamespace(
            authorizationStatusForEntityType_=staticmethod(lambda _entity_type: 3),
            alloc=lambda: fake_store,
        ),
    )
    monkeypatch.setattr(calendar_events, "EventKit", fake_eventkit)
    monkeypatch.setattr(calendar_events, "_calendar_available", lambda: True)


def _insert_calendar_link(
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
            INSERT INTO calendar_event_links (
                id, task_id, external_id, sync_status, conflict_status,
                last_synced_at, source_modified_at, tombstoned_at
            ) VALUES (?, ?, ?, 'linked', 'none', ?, ?, NULL)
            """,
            (f"link-{task_id}", task_id, external_id, last_synced_at, source_modified_at),
        )


def _fetch_calendar_link(db_path: Any, task_id: str) -> Any:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT sync_status, conflict_status
            FROM calendar_event_links
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    return {"sync_status": row[0], "conflict_status": row[1]}
