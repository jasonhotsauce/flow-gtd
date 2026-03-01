"""Reusable empty-state rendering helpers for TUI screens."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence

_MARKUP_PATTERN = re.compile(r"\[[^\]]+\]")

DEFAULT_TIPS: tuple[str, ...] = (
    "Batch quick captures, then process them in one focused pass.",
    "Choose one clear next action before ending a work block.",
    "Use short context tags to keep related work easy to find.",
    "If a step takes under two minutes, finish it now.",
    "Capture quickly, then organize with a calm review pass.",
)

DEFAULT_ASCII_ANCHOR = r'''
   ___      _                            
  / __|    | |     ___    __ _    _ _    
 | (__     | |    / -_)  / _` |  | ' \   
  \___|   _|_|_   \___|  \__,_|  |_||_|  
_|"""""|_|"""""|_|"""""|_|"""""|_|"""""| 
"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-' 
'''


class TipsProvider:
    """Simple randomized tip provider."""

    def __init__(
        self,
        tips: Sequence[str] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._tips: tuple[str, ...] = tuple(tips) if tips else DEFAULT_TIPS
        self._rng = rng or random.Random()

    def next_tip(self) -> str:
        """Return a random productivity tip."""
        return self._rng.choice(self._tips)


class EmptyStateRenderer:
    """Render a centered, low-noise empty state with dynamic padding."""

    def __init__(
        self,
        tips_provider: TipsProvider | None = None,
        ascii_anchor: str | Sequence[str] | None = None,
    ) -> None:
        self._tips_provider = tips_provider or TipsProvider()
        self._ascii_anchor = self._normalize_anchor(ascii_anchor or DEFAULT_ASCII_ANCHOR)

    @staticmethod
    def _normalize_anchor(anchor: str | Sequence[str]) -> tuple[str, ...]:
        """Normalize anchor input to non-empty lines."""
        if isinstance(anchor, str):
            lines = [line.rstrip() for line in anchor.splitlines() if line.strip()]
            return tuple(lines) if lines else ("[empty]",)

        lines = [str(line).rstrip() for line in anchor if str(line).strip()]
        return tuple(lines) if lines else ("[empty]",)

    @staticmethod
    def calculate_padding(
        view_width: int,
        view_height: int,
        content_width: int,
        content_height: int,
    ) -> tuple[int, int]:
        """Calculate top/left padding to center content in available viewport."""
        safe_width = min(max(view_width, 24), 240)
        safe_height = min(max(view_height, 8), 80)
        # Keep padding bounded so runtime size anomalies can't push content off-screen.
        top = min(max((safe_height - content_height) // 2, 0), 6)
        left = min(max((safe_width - content_width) // 2, 0), 40)
        return top, left

    def render(
        self,
        *,
        view_width: int,
        view_height: int,
        status_header: str,
        cta_key: str,
        cta_action: str,
    ) -> str:
        """Build centered empty-state content."""
        tip = self._tips_provider.next_tip()
        styled_lines = [
            *(f"[#9fb2c4]{line}[/]" for line in self._ascii_anchor),
            "",
            f"[b #e7d7bf]{status_header}[/]",
            "",
            f"[black on #cdb38b][[{cta_key}]][/][#c7d2dd] {cta_action}[/]",
            "",
            f"[dim]Tip: {tip}[/]",
        ]

        # Keep padding computation as a reusable layout helper for screen-level sizing.
        plain_lines = [_MARKUP_PATTERN.sub("", line) for line in styled_lines]
        content_width = max((len(line) for line in plain_lines), default=0)
        _ = self.calculate_padding(
            view_width=view_width,
            view_height=view_height,
            content_width=content_width,
            content_height=len(plain_lines),
        )
        return "\n".join(styled_lines)
