"""Shared keybinding contract for TUI screens and modals."""

from __future__ import annotations

from typing import TypeAlias

Binding: TypeAlias = tuple[str, str, str]

QUIT_Q_BINDING: Binding = ("q", "quit", "Quit")
BACK_ESCAPE_BINDING: Binding = ("escape", "go_back", "Back")
HELP_BINDING: Binding = ("?", "show_help", "Help")
NAV_DOWN_BINDING: Binding = ("j", "cursor_down", "Down")
NAV_UP_BINDING: Binding = ("k", "cursor_up", "Up")

MODAL_CANCEL_ESCAPE_BINDING: Binding = ("escape", "cancel", "Cancel")
MODAL_NAV_DOWN_BINDING: Binding = ("j", "cursor_down", "Down")
MODAL_NAV_UP_BINDING: Binding = ("k", "cursor_up", "Up")


def compose_bindings(*bindings: Binding) -> list[Binding]:
    """Return keybinding tuples in order."""
    return list(bindings)


def with_global_bindings(*bindings: Binding) -> list[Binding]:
    """Prefix bindings with the global screen contract."""
    return compose_bindings(
        QUIT_Q_BINDING,
        BACK_ESCAPE_BINDING,
        NAV_DOWN_BINDING,
        NAV_UP_BINDING,
        HELP_BINDING,
        *bindings,
    )


def with_modal_bindings(*bindings: Binding) -> list[Binding]:
    """Prefix bindings with the global modal contract."""
    return compose_bindings(
        MODAL_CANCEL_ESCAPE_BINDING,
        MODAL_NAV_DOWN_BINDING,
        MODAL_NAV_UP_BINDING,
        *bindings,
    )
