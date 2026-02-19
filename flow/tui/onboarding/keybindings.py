"""Shared keybinding contract for onboarding screens."""

from __future__ import annotations

from typing import TypeAlias

Binding: TypeAlias = tuple[str, str, str]

QUIT_ESCAPE_BINDING: Binding = ("escape", "quit", "Quit")
QUIT_Q_BINDING: Binding = ("q", "quit", "Quit")
BACK_ESCAPE_BINDING: Binding = ("escape", "go_back", "Back")
BACK_CTRL_B_BINDING: Binding = ("ctrl+b", "go_back", "Back")
NAV_DOWN_J_BINDING: Binding = ("j", "cursor_down", "Down")
NAV_UP_K_BINDING: Binding = ("k", "cursor_up", "Up")
CONFIRM_C_BINDING: Binding = ("c", "confirm", "Continue")
CONFIRM_ENTER_BINDING: Binding = ("enter", "confirm", "Continue")
SUBMIT_ENTER_BINDING: Binding = ("enter", "submit", "Continue")
RETRY_R_BINDING: Binding = ("r", "retry", "Retry")
START_FLOW_ENTER_BINDING: Binding = ("enter", "start_flow", "Start Flow")


def compose_bindings(*bindings: Binding) -> list[Binding]:
    """Return binding tuples in order.

    This is a small hook for future onboarding keybinding composition work.
    """
    return list(bindings)
