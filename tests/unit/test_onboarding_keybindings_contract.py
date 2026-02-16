"""Contract tests for shared onboarding keybindings."""

from __future__ import annotations

from flow.tui.onboarding import keybindings
from flow.tui.onboarding.screens.credentials import CredentialsScreen
from flow.tui.onboarding.screens.first_capture import FirstCaptureScreen
from flow.tui.onboarding.screens.provider import ProviderSelectScreen
from flow.tui.onboarding.screens.validation import ValidationScreen


def test_keybindings_contract_exports_expected_hooks() -> None:
    """Shared keybinding module should expose hook and constants."""
    assert callable(keybindings.compose_bindings)

    assert keybindings.QUIT_ESCAPE_BINDING == ("escape", "go_back", "Back")
    assert keybindings.QUIT_Q_BINDING == ("q", "quit", "Quit")
    assert keybindings.BACK_ESCAPE_BINDING == ("escape", "go_back", "Back")
    assert keybindings.BACK_CTRL_B_BINDING == ("ctrl+b", "go_back", "Back")


def test_provider_bindings_match_contract() -> None:
    """Provider screen should use shared onboarding binding contract."""
    assert ProviderSelectScreen.BINDINGS == keybindings.compose_bindings(
        keybindings.QUIT_ESCAPE_BINDING,
        keybindings.QUIT_Q_BINDING,
        keybindings.NAV_DOWN_J_BINDING,
        keybindings.NAV_UP_K_BINDING,
        keybindings.CONFIRM_ENTER_BINDING,
        keybindings.CONFIRM_C_BINDING,
    )


def test_credentials_bindings_match_contract() -> None:
    """Credentials screen should use shared onboarding binding contract."""
    assert CredentialsScreen.BINDINGS == keybindings.compose_bindings(
        keybindings.BACK_ESCAPE_BINDING,
        keybindings.BACK_CTRL_B_BINDING,
        keybindings.SUBMIT_ENTER_BINDING,
    )


def test_validation_bindings_match_contract() -> None:
    """Validation screen should use shared onboarding binding contract."""
    assert ValidationScreen.BINDINGS == keybindings.compose_bindings(
        keybindings.BACK_ESCAPE_BINDING,
        keybindings.RETRY_R_BINDING,
        keybindings.START_FLOW_ENTER_BINDING,
    )


def test_first_capture_screen_keeps_escape_skip_and_global_quit() -> None:
    """First capture should keep skip behavior while exposing global quit."""
    keys = {
        binding[0] if isinstance(binding, tuple) else binding.key
        for binding in FirstCaptureScreen.BINDINGS
    }
    assert "escape" in keys
    assert "q" in keys
