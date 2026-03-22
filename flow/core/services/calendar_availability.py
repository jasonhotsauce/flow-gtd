"""Compact calendar availability service for workspace recommendations."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from flow.core.focus import CalendarAvailability

if sys.platform == "darwin":
    import EventKit  # type: ignore[import-not-found]
    from Foundation import NSDate  # type: ignore[import-not-found]
else:
    EventKit = None  # type: ignore[assignment]
    NSDate = None  # type: ignore[assignment]

_CACHE_TTL_SECONDS = 300
_cache: tuple[float, CalendarAvailability] | None = None
_cache_lock = threading.Lock()


def get_calendar_availability() -> CalendarAvailability:
    """Return a compact calendar summary for recommendation heuristics."""
    cached = _get_cached_summary()
    if cached is not None:
        return cached

    summary = _fetch_calendar_availability()
    with _cache_lock:
        global _cache
        _cache = (time.time(), summary)
    return summary


def _get_cached_summary() -> CalendarAvailability | None:
    with _cache_lock:
        if _cache is None:
            return None
        cached_at, summary = _cache
        if time.time() - cached_at >= _CACHE_TTL_SECONDS:
            return None
        return summary


def _fetch_calendar_availability() -> CalendarAvailability:
    if sys.platform != "darwin" or EventKit is None or NSDate is None:
        return _unavailable()

    try:
        store = EventKit.EKEventStore.alloc().init()
        entity_type = 0  # EKEntityTypeEvent

        done = threading.Event()
        granted_result = [None]

        def completion(granted_flag: bool, _error: object | None) -> None:
            granted_result[0] = granted_flag
            done.set()

        store.requestAccessToEntityType_completion_(entity_type, completion)
        done.wait(timeout=10.0)
        if granted_result[0] is not True:
            return _unavailable()

        calendars = store.calendarsForEntityType_(entity_type)
        if not calendars:
            return CalendarAvailability(
                available=True,
                next_free_window_minutes=None,
                minutes_until_next_event=None,
            )

        now = datetime.now(timezone.utc)
        end_of_search = now + timedelta(hours=24)
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            _datetime_to_nsdate(now),
            _datetime_to_nsdate(end_of_search),
            calendars,
        )
        events = store.eventsMatchingPredicate_(predicate)
        if not events:
            return CalendarAvailability(
                available=True,
                next_free_window_minutes=None,
                minutes_until_next_event=None,
            )

        next_event_start: datetime | None = None
        for event in events:
            start = _nsdate_to_datetime(event.startDate())
            if start is None or start <= now:
                continue
            if next_event_start is None or start < next_event_start:
                next_event_start = start

        if next_event_start is None:
            return CalendarAvailability(
                available=True,
                next_free_window_minutes=None,
                minutes_until_next_event=None,
            )

        minutes_until_next_event = max(
            0, int((next_event_start - now).total_seconds() // 60)
        )
        return CalendarAvailability(
            available=True,
            next_free_window_minutes=minutes_until_next_event,
            minutes_until_next_event=minutes_until_next_event,
        )
    except Exception:
        return _unavailable()


def _datetime_to_nsdate(dt: datetime) -> NSDate | None:
    try:
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())
    except Exception:
        return None


def _nsdate_to_datetime(nsdate: NSDate | None) -> datetime | None:
    if nsdate is None:
        return None
    try:
        return datetime.fromtimestamp(nsdate.timeIntervalSince1970(), tz=timezone.utc)
    except Exception:
        return None


def _unavailable() -> CalendarAvailability:
    return CalendarAvailability(
        available=False,
        next_free_window_minutes=None,
        minutes_until_next_event=None,
    )
