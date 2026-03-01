from __future__ import annotations

import random

from flow.tui.common.widgets.empty_state import EmptyStateRenderer, TipsProvider


def test_tips_provider_returns_tip_from_configured_pool() -> None:
    provider = TipsProvider(
        tips=["Tip A", "Tip B", "Tip C"],
        rng=random.Random(1),
    )

    assert provider.next_tip() in {"Tip A", "Tip B", "Tip C"}


def test_empty_state_layout_calculates_center_padding() -> None:
    top, left = EmptyStateRenderer.calculate_padding(
        view_width=80,
        view_height=24,
        content_width=20,
        content_height=8,
    )

    assert top == 6
    assert left == 30


def test_empty_state_render_contains_anchor_header_cta_and_tip() -> None:
    renderer = EmptyStateRenderer(tips_provider=TipsProvider(tips=["Use 2-minute rule"], rng=random.Random(1)))

    rendered = renderer.render(
        view_width=70,
        view_height=20,
        status_header="No Active Tasks",
        cta_key="N",
        cta_action="Create New Inbox Task",
    )

    assert "No Active Tasks" in rendered
    assert "Create New Inbox Task" in rendered
    assert "Use 2-minute rule" in rendered
    assert "[" in rendered and "]" in rendered
    assert not rendered.startswith("\n")


def test_empty_state_accepts_multiline_string_anchor() -> None:
    renderer = EmptyStateRenderer(
        tips_provider=TipsProvider(tips=["Tip A"], rng=random.Random(1)),
        ascii_anchor="line-1\nline-2\nline-3",
    )

    rendered = renderer.render(
        view_width=70,
        view_height=20,
        status_header="No Active Tasks",
        cta_key="N",
        cta_action="Create New Inbox Task",
    )

    assert "line-1" in rendered
    assert "line-2" in rendered
    assert "line-3" in rendered
