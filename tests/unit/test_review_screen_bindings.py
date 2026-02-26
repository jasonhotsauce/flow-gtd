"""Unit tests for Review screen key bindings."""

from __future__ import annotations

from flow.tui.common.base_screen import FlowScreen
from flow.tui.screens.review.review import ReviewScreen


def test_review_screen_inherits_flow_screen() -> None:
    """Review screen should inherit shared FlowScreen contract."""
    assert issubclass(ReviewScreen, FlowScreen)


def test_review_screen_has_global_quit_binding() -> None:
    """Review screen should expose shared quit key binding."""
    assert any(
        (binding[0] == "q" if isinstance(binding, tuple) else binding.key == "q")
        for binding in ReviewScreen.BINDINGS
    )


def test_review_screen_resurface_action_only_available_in_someday_mode() -> None:
    """Resurface should only be available while viewing Someday items."""
    screen = ReviewScreen()

    screen._mode = "stale"
    assert screen.check_action("resurface", ()) is False

    screen._mode = "report"
    assert screen.check_action("resurface", ()) is False

    screen._mode = "someday"
    assert screen.check_action("resurface", ()) is True
