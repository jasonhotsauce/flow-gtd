"""Regression tests for Apple Reminders sync behavior."""

from __future__ import annotations

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
    ) -> None:
        self._ek_id = ek_id
        self._title = title
        self._completed = completed
        self._calendar = SimpleNamespace(title=lambda: calendar_title)

    def isCompleted(self) -> bool:
        return self._completed

    def calendarItemIdentifier(self) -> str:
        return self._ek_id

    def title(self) -> str:
        return self._title

    def calendar(self) -> SimpleNamespace:
        return self._calendar


class _FakeStore:
    def __init__(self, reminder_list: list[_FakeReminder]) -> None:
        self._reminder_list = reminder_list

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
