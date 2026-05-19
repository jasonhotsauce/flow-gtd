"""macOS EventKit bridge for bi-directional sync with Apple Reminders."""

import sqlite3
import sys
import threading
import uuid as _uuid
from datetime import datetime, timezone
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
_RECENTLY_DELETED_CALENDAR = "recently deleted"


def _reminders_available() -> bool:
    return sys.platform == "darwin" and EventKit is not None


def _calendar_title(reminder: object) -> str:
    """Return the normalized title for a reminder calendar, if available."""
    calendar = getattr(reminder, "calendar", lambda: None)()
    if calendar is None:
        return ""
    raw_title = getattr(calendar, "title", lambda: "")()
    return str(raw_title).strip().casefold()


def _reminder_modified_token(reminder: object) -> str | None:
    """Return a stable string token for EventKit source modification state."""
    raw_value = getattr(reminder, "lastModifiedDate", lambda: None)()
    if raw_value is None:
        return None
    interval = getattr(raw_value, "timeIntervalSince1970", None)
    if callable(interval):
        return datetime.fromtimestamp(float(interval()), tz=timezone.utc).isoformat()
    return str(raw_value)


def _now_token() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_reminder_link(
    db_path: Path,
    *,
    task_id: str,
    external_id: str,
    source_modified_at: str | None,
) -> None:
    now = _now_token()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reminder_links (
                id, task_id, external_id, sync_status, conflict_status,
                last_synced_at, source_modified_at, tombstoned_at
            ) VALUES (?, ?, ?, 'synced', 'none', ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
                sync_status = excluded.sync_status,
                conflict_status = excluded.conflict_status,
                last_synced_at = excluded.last_synced_at,
                source_modified_at = excluded.source_modified_at,
                tombstoned_at = NULL
            """,
            (
                f"reminder:{external_id}",
                task_id,
                external_id,
                now,
                source_modified_at,
            ),
        )


def _mark_reminder_link_conflict(db_path: Path, *, task_id: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE reminder_links
            SET sync_status = 'conflict', conflict_status = 'source_changed'
            WHERE task_id = ?
            """,
            (task_id,),
        )


def _mark_reminder_link_synced(
    db_path: Path,
    *,
    task_id: str,
    source_modified_at: str | None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE reminder_links
            SET sync_status = 'synced',
                conflict_status = 'none',
                last_synced_at = ?,
                source_modified_at = ?
            WHERE task_id = ?
            """,
            (_now_token(), source_modified_at, task_id),
        )


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
        ek_id = rem.calendarItemIdentifier()
        if not ek_id:
            continue
        if _calendar_title(rem) == _RECENTLY_DELETED_CALENDAR:
            continue
        # Keep Flow aligned with active Reminders only.
        if rem.isCompleted():
            existing = db.get_item_by_ek_id(ek_id)
            if existing and existing.status not in {"done", "archived"}:
                db.update_item(existing.model_copy(update={"status": "archived"}))
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
        _upsert_reminder_link(
            db_path,
            task_id=item.id,
            external_id=ek_id,
            source_modified_at=_reminder_modified_token(rem),
        )
        count += 1
        # NOTE: We intentionally do NOT move reminders to Flow-Imported list.
        # EventKit has a bug where reminders with certain alarm configurations
        # crash in _fixAlarmUUIDsForClone:from: when moved to a new calendar.

    return count, f"Imported {count} incomplete reminders."


def sync_flow_to_reminders(db_path: Path, *, write_back: bool = False) -> tuple[int, str]:
    """
    Push linked Flow task changes back to Apple Reminders.

    Write-back is opt-in. If the source Reminder changed since the last recorded
    sync token, Flow marks the link as a conflict and does not overwrite it.
    """
    if not write_back:
        return 0, "Write-back disabled; no Apple Reminders were modified."
    if not _reminders_available():
        return 0, "Reminders write-back is only supported on macOS."

    status, status_desc = get_reminder_auth_status()
    if status != _EK_AUTH_FULL_ACCESS:
        return 0, f"Reminders write-back unavailable (status: {status_desc})."

    store = EventKit.EKEventStore.alloc().init()
    rows = _linked_flow_reminder_rows(db_path)
    written = 0
    conflicts = 0

    for row in rows:
        try:
            reminder = store.calendarItemWithIdentifier_(row["external_id"])
        except Exception:  # pragma: no cover - defensive PyObjC boundary
            reminder = None
        if reminder is None:
            _mark_reminder_link_conflict(db_path, task_id=row["task_id"])
            conflicts += 1
            continue

        source_modified_at = _reminder_modified_token(reminder)
        if (
            row["source_modified_at"]
            and source_modified_at
            and source_modified_at != row["source_modified_at"]
        ):
            _mark_reminder_link_conflict(db_path, task_id=row["task_id"])
            conflicts += 1
            continue

        if row["status"] == "archived":
            continue

        try:
            reminder.setTitle_(row["title"])
            reminder.setCompleted_(row["status"] == "done")
            save_result = store.saveReminder_commit_error_(reminder, True, None)
            saved = bool(save_result[0]) if isinstance(save_result, tuple) else bool(save_result)
        except Exception:  # pragma: no cover - defensive PyObjC boundary
            saved = False

        if saved:
            _mark_reminder_link_synced(
                db_path,
                task_id=row["task_id"],
                source_modified_at=_reminder_modified_token(reminder) or source_modified_at,
            )
            written += 1

    if conflicts:
        return written, f"Wrote {written} Flow changes to Apple Reminders; {conflicts} conflict(s) need review."
    suffix = "change" if written == 1 else "changes"
    return written, f"Wrote {written} Flow {suffix} to Apple Reminders."


def _linked_flow_reminder_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT
                i.id AS task_id,
                i.title,
                i.status,
                i.updated_at,
                rl.external_id,
                rl.source_modified_at,
                rl.last_synced_at
            FROM reminder_links rl
            JOIN items i ON i.id = rl.task_id
            WHERE rl.tombstoned_at IS NULL
              AND rl.conflict_status = 'none'
              AND (
                rl.last_synced_at IS NULL
                OR COALESCE(i.updated_at, i.created_at, '') > rl.last_synced_at
              )
            ORDER BY i.updated_at ASC
            """
        ).fetchall()
