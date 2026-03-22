"""Focus helpers for confirmed-plan recommendations."""

from dataclasses import dataclass
from typing import Literal
from typing import Optional

from flow.models import Item


@dataclass(frozen=True)
class ConfirmedFocusRecommendation:
    """A recommended confirmed-plan item for in-workspace execution."""

    item: Item
    bucket: Literal["top", "bonus"]
    position: int
    explanation: str


@dataclass(frozen=True)
class CalendarAvailability:
    """Compact calendar availability input for confirmed-plan recommendation."""

    available: bool
    next_free_window_minutes: int | None
    minutes_until_next_event: int | None


@dataclass(frozen=True)
class _RankedPlannedItem:
    item: Item
    bucket: Literal["top", "bonus"]
    position: int


def recommend_confirmed_focus(
    *,
    top_items: list[Item],
    bonus_items: list[Item],
    calendar_availability: CalendarAvailability | None = None,
) -> ConfirmedFocusRecommendation | None:
    """Return the next recommended confirmed-plan item.

    Only active confirmed-plan items are eligible. `Top 3` always outranks
    `Bonus`, and each bucket preserves its existing order for deterministic
    fallback behavior.
    """
    active_top = [
        _RankedPlannedItem(item=item, bucket="top", position=position)
        for position, item in enumerate(top_items)
        if item.status == "active"
    ]
    active_bonus = [
        _RankedPlannedItem(item=item, bucket="bonus", position=position)
        for position, item in enumerate(bonus_items)
        if item.status == "active"
    ]
    active_items = active_top + active_bonus
    if not active_items:
        return None

    if _can_use_calendar_fit(active_items, calendar_availability):
        fitting_top = _first_fitting_item(
            active_top, calendar_availability.next_free_window_minutes
        )
        if fitting_top is not None:
            return ConfirmedFocusRecommendation(
                item=fitting_top.item,
                bucket=fitting_top.bucket,
                position=fitting_top.position,
                explanation=(
                    f"Top 3 fit: {fitting_top.item.estimated_duration}m fits before the "
                    f"next event in {calendar_availability.minutes_until_next_event}m."
                ),
            )
        fitting_bonus = _first_fitting_item(
            active_bonus, calendar_availability.next_free_window_minutes
        )
        if fitting_bonus is not None:
            return ConfirmedFocusRecommendation(
                item=fitting_bonus.item,
                bucket=fitting_bonus.bucket,
                position=fitting_bonus.position,
                explanation=(
                    f"Bonus fit: no active Top 3 item fits the next "
                    f"{calendar_availability.next_free_window_minutes}m window."
                ),
            )

    explanation = _fallback_explanation(active_items, calendar_availability)
    selected = active_items[0]
    return ConfirmedFocusRecommendation(
        item=selected.item,
        bucket=selected.bucket,
        position=selected.position,
        explanation=explanation,
    )


def _can_use_calendar_fit(
    active_items: list[_RankedPlannedItem],
    calendar_availability: CalendarAvailability | None,
) -> bool:
    if (
        calendar_availability is None
        or not calendar_availability.available
        or calendar_availability.next_free_window_minutes is None
        or calendar_availability.minutes_until_next_event is None
    ):
        return False
    return all(item.item.estimated_duration is not None for item in active_items)


def _first_fitting_item(
    items: list[_RankedPlannedItem], next_free_window_minutes: int | None
) -> _RankedPlannedItem | None:
    if next_free_window_minutes is None:
        return None
    for ranked_item in items:
        duration = ranked_item.item.estimated_duration
        if duration is not None and duration <= next_free_window_minutes:
            return ranked_item
    return None


def _fallback_explanation(
    active_items: list[_RankedPlannedItem],
    calendar_availability: CalendarAvailability | None,
) -> str:
    selected = active_items[0]
    if calendar_availability is None or not calendar_availability.available:
        return "Calendar unavailable. Falling back to saved plan order."
    return (
        f"Using saved plan order for {selected.bucket.title()} because calendar fit "
        "metadata is incomplete."
    )
