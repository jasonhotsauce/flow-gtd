"""macOS EventKit bridge for Flow-owned calendar event creation."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "darwin":
    import EventKit  # type: ignore[import-not-found]
    from Foundation import NSDate  # type: ignore[import-not-found]
else:
    EventKit = None  # type: ignore[assignment]
    NSDate = None  # type: ignore[assignment]

_EK_AUTH_FULL_ACCESS = 3
_EVENT_ENTITY_TYPE = 0


def _calendar_available() -> bool:
    return sys.platform == "darwin" and EventKit is not None


def sync_flow_tasks_to_calendar(db_path: Path) -> tuple[int, str]:
    """Create or update Flow-owned calendar events for eligible local tasks."""
    if not _calendar_available():
        return 0, "Calendar event sync is only supported on macOS."

    status = EventKit.EKEventStore.authorizationStatusForEntityType_(_EVENT_ENTITY_TYPE)
    if status != _EK_AUTH_FULL_ACCESS:
        return 0, "Calendar event sync requires full calendar access."

    store = EventKit.EKEventStore.alloc().init()
    rows = _eligible_task_rows(db_path)
    written = 0
    conflicts = 0

    for row in rows:
        event = _event_for_row(store, row)
        if event is None:
            _mark_conflict(db_path, task_id=row["task_id"])
            conflicts += 1
            continue

        source_modified_at = _event_modified_token(event)
        if (
            row["source_modified_at"]
            and source_modified_at
            and source_modified_at != row["source_modified_at"]
        ):
            _mark_conflict(db_path, task_id=row["task_id"])
            conflicts += 1
            continue

        _apply_task_to_event(store, event, row)
        try:
            save_result = store.saveEvent_span_commit_error_(event, 0, True, None)
            saved = bool(save_result[0]) if isinstance(save_result, tuple) else bool(save_result)
        except Exception:  # pragma: no cover - defensive PyObjC boundary
            saved = False

        if saved:
            external_id = event.calendarItemIdentifier()
            _upsert_event_link(
                db_path,
                task_id=row["task_id"],
                external_id=external_id,
                source_modified_at=_event_modified_token(event) or source_modified_at,
            )
            written += 1

    if conflicts:
        return written, f"Created or updated {written} Flow calendar events; {conflicts} conflict(s) need review."
    suffix = "event" if written == 1 else "events"
    return written, f"Created or updated {written} Flow calendar {suffix}."


def _eligible_task_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT
                i.id AS task_id,
                i.title,
                i.due_date,
                i.estimated_duration,
                cel.external_id,
                cel.source_modified_at,
                cel.last_synced_at
            FROM items i
            LEFT JOIN calendar_event_links cel
                ON cel.task_id = i.id AND cel.tombstoned_at IS NULL
            WHERE i.status = 'active'
              AND i.due_date IS NOT NULL
              AND i.estimated_duration IS NOT NULL
              AND (cel.conflict_status IS NULL OR cel.conflict_status = 'none')
              AND (
                cel.last_synced_at IS NULL
                OR COALESCE(i.updated_at, i.created_at, '') > cel.last_synced_at
              )
            ORDER BY i.due_date ASC
            """
        ).fetchall()


def _event_for_row(store: object, row: sqlite3.Row) -> object | None:
    external_id = row["external_id"]
    if external_id:
        try:
            return store.calendarItemWithIdentifier_(external_id)
        except Exception:  # pragma: no cover - defensive PyObjC boundary
            return None
    try:
        return EventKit.EKEvent.eventWithEventStore_(store)
    except Exception:  # pragma: no cover - defensive PyObjC boundary
        return None


def _apply_task_to_event(store: object, event: object, row: sqlite3.Row) -> None:
    start = _parse_datetime(row["due_date"])
    duration = int(row["estimated_duration"] or 30)
    end = start + timedelta(minutes=max(5, duration))

    event.setTitle_(row["title"])
    event.setStartDate_(_datetime_to_eventkit_date(start))
    event.setEndDate_(_datetime_to_eventkit_date(end))
    if not row["external_id"]:
        event.setCalendar_(store.defaultCalendarForNewEvents())


def _parse_datetime(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _datetime_to_eventkit_date(value: datetime) -> object:
    if NSDate is None:
        return value
    try:
        return NSDate.dateWithTimeIntervalSince1970_(value.timestamp())
    except Exception:  # pragma: no cover - defensive PyObjC boundary
        return value


def _event_modified_token(event: object) -> str | None:
    raw_value = getattr(event, "lastModifiedDate", lambda: None)()
    if raw_value is None:
        return None
    interval = getattr(raw_value, "timeIntervalSince1970", None)
    if callable(interval):
        return datetime.fromtimestamp(float(interval()), tz=timezone.utc).isoformat()
    return str(raw_value)


def _now_token() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_event_link(
    db_path: Path,
    *,
    task_id: str,
    external_id: str,
    source_modified_at: str | None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO calendar_event_links (
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
                f"calendar:{task_id}",
                task_id,
                external_id,
                _now_token(),
                source_modified_at,
            ),
        )


def _mark_conflict(db_path: Path, *, task_id: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE calendar_event_links
            SET sync_status = 'conflict', conflict_status = 'source_changed'
            WHERE task_id = ?
            """,
            (task_id,),
        )
