"""Unit tests for confirmed-plan focus recommendation behavior."""

from flow.core.focus import CalendarAvailability, recommend_confirmed_focus
from flow.models import Item


def test_recommend_confirmed_focus_uses_next_free_window_for_active_top_items() -> None:
    """Calendar-aware recommendation should pick the active Top 3 item that fits next."""
    recommendation = recommend_confirmed_focus(
        top_items=[
            Item(
                id="top-long",
                type="action",
                title="Long top",
                status="active",
                estimated_duration=50,
            ),
            Item(
                id="top-fit",
                type="action",
                title="Fitting top",
                status="active",
                estimated_duration=25,
            ),
        ],
        bonus_items=[
            Item(
                id="bonus-fit",
                type="action",
                title="Fitting bonus",
                status="active",
                estimated_duration=20,
            )
        ],
        calendar_availability=CalendarAvailability(
            available=True,
            next_free_window_minutes=30,
            minutes_until_next_event=30,
        ),
    )

    assert recommendation is not None
    assert recommendation.item.id == "top-fit"
    assert recommendation.bucket == "top"
    assert "30" in recommendation.explanation


def test_recommend_confirmed_focus_allows_bonus_only_when_no_active_top_fits() -> None:
    """Bonus can win only when no active Top 3 item fits the next free window."""
    recommendation = recommend_confirmed_focus(
        top_items=[
            Item(
                id="top-too-long",
                type="action",
                title="Top",
                status="active",
                estimated_duration=45,
            ),
        ],
        bonus_items=[
            Item(
                id="bonus-fit",
                type="action",
                title="Bonus",
                status="active",
                estimated_duration=20,
            ),
        ],
        calendar_availability=CalendarAvailability(
            available=True,
            next_free_window_minutes=30,
            minutes_until_next_event=30,
        ),
    )

    assert recommendation is not None
    assert recommendation.item.id == "bonus-fit"
    assert recommendation.bucket == "bonus"
    assert "Bonus" in recommendation.explanation


def test_recommend_confirmed_focus_falls_back_to_saved_order_when_metadata_is_sparse() -> None:
    """Sparse duration metadata should preserve saved confirmed-plan order."""
    recommendation = recommend_confirmed_focus(
        top_items=[
            Item(id="top-unknown", type="action", title="Unknown", status="active"),
            Item(
                id="top-fit",
                type="action",
                title="Known fit",
                status="active",
                estimated_duration=15,
            ),
        ],
        bonus_items=[
            Item(
                id="bonus-fit",
                type="action",
                title="Bonus",
                status="active",
                estimated_duration=10,
            ),
        ],
        calendar_availability=CalendarAvailability(
            available=True,
            next_free_window_minutes=20,
            minutes_until_next_event=20,
        ),
    )

    assert recommendation is not None
    assert recommendation.item.id == "top-unknown"
    assert recommendation.bucket == "top"
    assert "plan order" in recommendation.explanation.lower()


def test_recommend_confirmed_focus_returns_explanation_for_fallback_selection() -> None:
    """Recommendation result should include a short explanation string for the UI."""
    recommendation = recommend_confirmed_focus(
        top_items=[
            Item(id="top-1", type="action", title="First in plan", status="active"),
        ],
        bonus_items=[
            Item(id="bonus-1", type="action", title="Bonus", status="active"),
        ],
        calendar_availability=CalendarAvailability(
            available=False,
            next_free_window_minutes=None,
            minutes_until_next_event=None,
        ),
    )

    assert recommendation is not None
    assert recommendation.item.id == "top-1"
    assert recommendation.position == 0
    assert recommendation.explanation
