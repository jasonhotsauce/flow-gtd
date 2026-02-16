"""Shared keybinding contract for onboarding screens."""

from __future__ import annotations

from flow.tui.common.keybindings import (
    BACK_ESCAPE_BINDING as GLOBAL_BACK_ESCAPE_BINDING,
    NAV_DOWN_BINDING as GLOBAL_NAV_DOWN_BINDING,
    NAV_UP_BINDING as GLOBAL_NAV_UP_BINDING,
    QUIT_Q_BINDING as GLOBAL_QUIT_Q_BINDING,
    compose_bindings,
)

Binding = tuple[str, str, str]

QUIT_ESCAPE_BINDING: Binding = GLOBAL_BACK_ESCAPE_BINDING
QUIT_Q_BINDING: Binding = GLOBAL_QUIT_Q_BINDING
BACK_ESCAPE_BINDING: Binding = GLOBAL_BACK_ESCAPE_BINDING
BACK_CTRL_B_BINDING: Binding = ("ctrl+b", "go_back", "Back")
NAV_DOWN_J_BINDING: Binding = GLOBAL_NAV_DOWN_BINDING
NAV_UP_K_BINDING: Binding = GLOBAL_NAV_UP_BINDING
CONFIRM_C_BINDING: Binding = ("c", "confirm", "Continue")
CONFIRM_ENTER_BINDING: Binding = ("enter", "confirm", "Continue")
SUBMIT_ENTER_BINDING: Binding = ("enter", "submit", "Continue")
RETRY_R_BINDING: Binding = ("r", "retry", "Retry")
START_FLOW_ENTER_BINDING: Binding = ("enter", "start_flow", "Start Flow")
