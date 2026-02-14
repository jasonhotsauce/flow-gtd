"""Unit tests for defer date parsing utility."""

from datetime import datetime

from flow.core.defer_utils import parse_defer_until


def test_parse_tomorrow_returns_9am_local() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("tomorrow", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-15"
    assert result.hour == 9


def test_parse_next_week_returns_same_weekday_9am() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("next week", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-21"
    assert result.hour == 9


def test_parse_explicit_date() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("2026-02-20", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-20"
    assert result.hour == 9


def test_parse_explicit_datetime() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("2026-02-20 13:45", now)
    assert result is not None
    assert result.hour == 13
    assert result.minute == 45


def test_parse_invalid_returns_none() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    assert parse_defer_until("someday maybe", now) is None
