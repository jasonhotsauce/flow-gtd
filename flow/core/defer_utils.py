"""Utilities for parsing Defer Until date/time input."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

DEFAULT_DEFER_HOUR = 9


def parse_defer_until(raw: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse Defer Until input into a local datetime.

    Accepted values:
    - tomorrow
    - next week
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM
    """
    value = raw.strip().lower()
    current = now or datetime.now()

    if value == "tomorrow":
        target = current + timedelta(days=1)
        return target.replace(
            hour=DEFAULT_DEFER_HOUR, minute=0, second=0, microsecond=0
        )

    if value == "next week":
        target = current + timedelta(days=7)
        return target.replace(
            hour=DEFAULT_DEFER_HOUR, minute=0, second=0, microsecond=0
        )

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw.strip(), fmt)
            if fmt == "%Y-%m-%d":
                return parsed.replace(
                    hour=DEFAULT_DEFER_HOUR, minute=0, second=0, microsecond=0
                )
            return parsed
        except ValueError:
            continue

    return None
