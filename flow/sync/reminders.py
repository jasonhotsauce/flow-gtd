"""macOS EventKit bridge for bi-directional sync with Apple Reminders."""

import sys
import threading
import uuid as _uuid
from pathlib import Path
from typing import Callable, Optional

from flow.database.sqlite import SqliteDB
from flow.models import Item

if sys.platform == "darwin":
    import EventKit  # pylint: disable=invalid-name
else:
    EventKit = None  # type: ignore  # pylint: disable=invalid-name

FLOW_IMPORTED_LIST_NAME = "Flow-Imported"


def _reminders_available() -> bool:
    return sys.platform == "darwin" and EventKit is not None


def request_reminder_access(
    callback: Optional[Callable[[bool, Optional[object]], None]] = None,
) -> bool:
    """Request Reminders authorization. Returns True if granted. On non-darwin returns False."""
    if not _reminders_available():
        return False
    store = EventKit.EKEventStore.alloc().init()
    entity_type = 1  # EKEntityTypeReminder
    done = threading.Event()
    result = [False]

    def completion(granted_flag: bool, _error: Optional[object]) -> None:
        result[0] = granted_flag
        if callback:
            callback(granted_flag, _error)
        done.set()

    store.requestAccessToEntityType_completion_(entity_type, completion)
    done.wait(timeout=10.0)
    return result[0]


def sync_reminders_to_flow(db_path: Path) -> tuple[int, str]:
    """
    Pull reminders from Apple Reminders into Flow SQLite.
    Fetches all reminders, maps to Item, insert/update by original_ek_id.
    Moves imported reminders to 'Flow-Imported' list (never delete).
    Returns (count_imported, message).
    """
    if not _reminders_available():
        return 0, "Reminders sync is only supported on macOS."

    store = EventKit.EKEventStore.alloc().init()
    entity_type = 1  # EKEntityTypeReminder
    done = threading.Event()
    granted_result = [None]

    def completion(granted_flag: bool, _error: Optional[object]) -> None:
        granted_result[0] = granted_flag
        done.set()

    store.requestAccessToEntityType_completion_(entity_type, completion)
    done.wait(timeout=10.0)
    if granted_result[0] is not True:
        return 0, "Reminder access denied or not determined."

    # Get all reminder calendars
    calendars = store.calendarsForEntityType_(entity_type)
    if not calendars:
        return 0, "No reminder calendars found."

    # Predicate for all reminders in these calendars
    predicate = store.predicateForRemindersInCalendars_(calendars)
    results = [None]
    fetch_done = threading.Event()

    def fetch_done_cb(reminders: object) -> None:
        results[0] = reminders
        fetch_done.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_done_cb)
    fetch_done.wait(timeout=15.0)

    reminder_list = results[0]
    if reminder_list is None:
        return 0, "Failed to fetch reminders."

    # Find or create "Flow-Imported" calendar (reminder list)
    flow_calendar = None
    for cal in calendars:
        if cal.title() == FLOW_IMPORTED_LIST_NAME:
            flow_calendar = cal
            break
    if flow_calendar is None:
        flow_calendar = EventKit.EKCalendar.calendarForEntityType_eventStore_(
            entity_type, store
        )
        flow_calendar.setTitle_(FLOW_IMPORTED_LIST_NAME)
        source = (
            store.defaultCalendarForNewReminders().source()
            if store.defaultCalendarForNewReminders()
            else None
        )
        if source:
            flow_calendar.setSource_(source)
        try:
            store.saveCalendar_commit_error_(flow_calendar, True, None)
        except Exception:
            pass  # best-effort

    db = SqliteDB(db_path)
    db.init_db()
    count = 0
    for rem in reminder_list:  # pylint: disable=not-an-iterable
        ek_id = rem.calendarItemIdentifier()
        if not ek_id:
            continue
        title = rem.title() or ""
        completed = rem.isCompleted()
        existing = db.get_item_by_ek_id(ek_id)
        if existing:
            item = existing.model_copy(
                update={"title": title, "status": "archived" if completed else "active"}
            )
            db.update_item(item)
        else:
            item = Item(
                id=str(_uuid.uuid4()),
                type="inbox",
                title=title,
                status="archived" if completed else "active",
                original_ek_id=ek_id,
            )
            db.insert_inbox(item)
        count += 1
        # Move to Flow-Imported list (do not delete)
        if flow_calendar and rem.calendar() != flow_calendar:
            try:
                rem.setCalendar_(flow_calendar)
                store.saveReminder_commit_error_(rem, True, None)
            except Exception:
                pass

    return count, f"Imported {count} reminders."
