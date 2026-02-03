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

# Authorization status constants
_EK_AUTH_NOT_DETERMINED = 0
_EK_AUTH_RESTRICTED = 1
_EK_AUTH_DENIED = 2
_EK_AUTH_FULL_ACCESS = 3  # macOS 14+ (was "Authorized" = 3 pre-Sonoma)
_EK_AUTH_WRITE_ONLY = 4  # macOS 14+


def _reminders_available() -> bool:
    return sys.platform == "darwin" and EventKit is not None


def get_reminder_auth_status() -> tuple[int, str]:
    """Get current Reminders authorization status. Returns (status_code, description)."""
    if not _reminders_available():
        return -1, "Not on macOS"
    entity_type = 1  # EKEntityTypeReminder
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(entity_type)
    status_names = {
        _EK_AUTH_NOT_DETERMINED: "Not Determined (never requested)",
        _EK_AUTH_RESTRICTED: "Restricted (parental controls/MDM)",
        _EK_AUTH_DENIED: "Denied",
        _EK_AUTH_FULL_ACCESS: "Full Access",
        _EK_AUTH_WRITE_ONLY: "Write Only",
    }
    return status, status_names.get(status, f"Unknown ({status})")


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
    Pull incomplete reminders from Apple Reminders into Flow SQLite inbox.
    Only imports reminders not yet completed (active tasks).
    Returns (count_imported, message).
    """
    if not _reminders_available():
        return 0, "Reminders sync is only supported on macOS."

    # Check current status first for better diagnostics
    current_status, status_desc = get_reminder_auth_status()

    store = EventKit.EKEventStore.alloc().init()
    entity_type = 1  # EKEntityTypeReminder
    done = threading.Event()
    granted_result = [None]
    error_result = [None]

    def completion(granted_flag: bool, error: Optional[object]) -> None:
        granted_result[0] = granted_flag
        error_result[0] = error
        done.set()

    # Use newer API on macOS 14+ if available
    if hasattr(store, "requestFullAccessToRemindersWithCompletion_"):
        store.requestFullAccessToRemindersWithCompletion_(completion)
    else:
        store.requestAccessToEntityType_completion_(entity_type, completion)

    done.wait(timeout=10.0)

    if granted_result[0] is not True:
        error_info = f" Error: {error_result[0]}" if error_result[0] else ""
        if current_status == _EK_AUTH_NOT_DETERMINED:
            return 0, (
                f"Reminders permission not yet granted (status: {status_desc}).{error_info}\n"
                "Try running from Terminal.app (not IDE terminal) to trigger the permission dialog.\n"
                "Or manually add Terminal to: System Settings → Privacy & Security → Reminders"
            )
        elif current_status == _EK_AUTH_DENIED:
            return 0, (
                f"Reminders access was denied (status: {status_desc}).{error_info}\n"
                "To fix:\n"
                "1. Open: System Settings → Privacy & Security → Reminders\n"
                "2. Enable access for Terminal (or your terminal app)\n"
                "Or reset with: tccutil reset Reminders"
            )
        elif current_status == _EK_AUTH_RESTRICTED:
            return 0, (
                f"Reminders access is restricted (status: {status_desc}).{error_info}\n"
                "This may be due to parental controls or device management (MDM)."
            )
        else:
            return 0, (
                f"Reminder access issue (status: {status_desc}).{error_info}\n"
                "Grant access in: System Settings → Privacy & Security → Reminders"
            )

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

    db = SqliteDB(db_path)
    db.init_db()
    count = 0
    for rem in reminder_list:  # pylint: disable=not-an-iterable
        # Only import incomplete reminders (skip completed ones)
        if rem.isCompleted():
            continue
        ek_id = rem.calendarItemIdentifier()
        if not ek_id:
            continue
        title = rem.title() or ""
        existing = db.get_item_by_ek_id(ek_id)
        if existing:
            item = existing.model_copy(update={"title": title, "status": "active"})
            db.update_item(item)
        else:
            item = Item(
                id=str(_uuid.uuid4()),
                type="inbox",
                title=title,
                status="active",
                original_ek_id=ek_id,
            )
            db.insert_inbox(item)
        count += 1
        # NOTE: We intentionally do NOT move reminders to Flow-Imported list.
        # EventKit has a bug where reminders with certain alarm configurations
        # crash in _fixAlarmUUIDsForClone:from: when moved to a new calendar.

    return count, f"Imported {count} incomplete reminders."
