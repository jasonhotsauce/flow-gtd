"""macOS EventKit bridge for reading calendar events (Focus Mode)."""

import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

if sys.platform == "darwin":
    import EventKit  # type: ignore[import-not-found]
    from Foundation import NSDate  # type: ignore[import-not-found]
else:
    EventKit = None  # type: ignore[assignment]
    NSDate = None  # type: ignore[assignment]

# Module-level cache for calendar events
_cache: dict[str, tuple[float, Optional["CalendarEvent"]]] = {}
_cache_lock = threading.Lock()
DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class CalendarEvent:
    """Represents an upcoming calendar event."""

    title: str
    start_time: datetime
    minutes_until_start: int


def _calendar_available() -> bool:
    """Check if EventKit calendar is available (macOS only)."""
    return sys.platform == "darwin" and EventKit is not None


def _nsdate_to_datetime(nsdate: "NSDate | None") -> Optional[datetime]:
    """Convert NSDate to Python datetime."""
    if nsdate is None:
        return None
    try:
        timestamp = nsdate.timeIntervalSince1970()
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except Exception:
        return None


def _datetime_to_nsdate(dt: datetime) -> "NSDate | None":
    """Convert Python datetime to NSDate."""
    if NSDate is None:
        return None
    try:
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())
    except Exception:
        return None


def get_next_event(
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> Optional[CalendarEvent]:
    """
    Query EventKit for the next calendar event.

    Returns None if:
    - Not on macOS
    - No calendar access granted
    - No upcoming events today

    Uses module-level cache with TTL to avoid excessive EventKit queries.
    Thread-safe for TUI usage.

    Args:
        cache_ttl_seconds: How long to cache the result (default 5 minutes).

    Returns:
        CalendarEvent with title, start_time, and minutes_until_start, or None.
    """
    if not _calendar_available():
        return None

    # Check cache first
    cache_key = "next_event"
    with _cache_lock:
        if cache_key in _cache:
            cached_time, cached_event = _cache[cache_key]
            if time.time() - cached_time < cache_ttl_seconds:
                # Recalculate minutes_until_start for cached event
                if cached_event is not None:
                    now = datetime.now(timezone.utc)
                    mins = int((cached_event.start_time - now).total_seconds() / 60)
                    if mins > 0:
                        return CalendarEvent(
                            title=cached_event.title,
                            start_time=cached_event.start_time,
                            minutes_until_start=mins,
                        )
                    # Event has passed, invalidate cache
                    del _cache[cache_key]
                else:
                    return None

    # Fetch from EventKit
    event = _fetch_next_event_from_eventkit()

    # Update cache
    with _cache_lock:
        _cache[cache_key] = (time.time(), event)

    return event


def _fetch_next_event_from_eventkit() -> Optional[CalendarEvent]:
    """Internal: fetch the next event from EventKit (no caching)."""
    try:
        store = EventKit.EKEventStore.alloc().init()
        entity_type = 0  # EKEntityTypeEvent (not Reminder)

        # Request calendar access
        done = threading.Event()
        granted_result = [None]

        def completion(granted_flag: bool, _error: Optional[object]) -> None:
            granted_result[0] = granted_flag
            done.set()

        store.requestAccessToEntityType_completion_(entity_type, completion)
        done.wait(timeout=10.0)

        if granted_result[0] is not True:
            return None

        # Get all calendars for events
        calendars = store.calendarsForEntityType_(entity_type)
        if not calendars:
            return None

        # Create time range: now to end of day (or next 24 hours)
        now = datetime.now(timezone.utc)
        end_of_search = now.replace(hour=23, minute=59, second=59)
        if end_of_search <= now:
            # If it's late, search into next day
            from datetime import timedelta

            end_of_search = now + timedelta(hours=24)

        start_nsdate = _datetime_to_nsdate(now)
        end_nsdate = _datetime_to_nsdate(end_of_search)

        if start_nsdate is None or end_nsdate is None:
            return None

        # Create predicate for events in time range
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            start_nsdate, end_nsdate, calendars
        )

        # Fetch events (synchronous for events, unlike reminders)
        events = store.eventsMatchingPredicate_(predicate)

        if not events or len(events) == 0:
            return None

        # Find the earliest upcoming event
        earliest_event = None
        earliest_start: Optional[datetime] = None

        for ev in events:
            try:
                start_date = ev.startDate()
                if start_date is None:
                    continue

                ev_start = _nsdate_to_datetime(start_date)
                if ev_start is None or ev_start <= now:
                    continue

                if earliest_start is None or ev_start < earliest_start:
                    earliest_start = ev_start
                    earliest_event = ev
            except Exception:
                continue

        if earliest_event is None or earliest_start is None:
            return None

        title = earliest_event.title() or "Untitled Event"
        minutes_until = int((earliest_start - now).total_seconds() / 60)

        return CalendarEvent(
            title=title,
            start_time=earliest_start,
            minutes_until_start=minutes_until,
        )

    except Exception:
        # Fail gracefully - never crash the app
        return None


def clear_cache() -> None:
    """Clear the event cache (for testing or forced refresh)."""
    with _cache_lock:
        _cache.clear()


def request_calendar_access() -> bool:
    """
    Request calendar authorization explicitly.

    Returns True if granted, False otherwise.
    On non-darwin platforms, returns False.
    """
    if not _calendar_available():
        return False

    try:
        store = EventKit.EKEventStore.alloc().init()
        entity_type = 0  # EKEntityTypeEvent
        done = threading.Event()
        result = [False]

        def completion(granted_flag: bool, _error: Optional[object]) -> None:
            result[0] = granted_flag
            done.set()

        store.requestAccessToEntityType_completion_(entity_type, completion)
        done.wait(timeout=10.0)
        return result[0]
    except Exception:
        return False
