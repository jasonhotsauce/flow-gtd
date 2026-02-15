"""Screen 1: LLM Provider Selection."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, RadioButton, RadioSet, Static

from flow.tui.onboarding.constants import PROVIDERS, PROVIDER_HINTS
from flow.tui.onboarding.keybindings import (
    CONFIRM_C_BINDING,
    CONFIRM_ENTER_BINDING,
    NAV_DOWN_J_BINDING,
    NAV_UP_K_BINDING,
    QUIT_ESCAPE_BINDING,
    QUIT_Q_BINDING,
    compose_bindings,
)

if TYPE_CHECKING:
    from flow.tui.onboarding.app import OnboardingApp


class ProviderSelectScreen(Screen):
    """Select an LLM provider for Flow GTD."""

    CSS_PATH = "provider.tcss"

    BINDINGS = compose_bindings(
        QUIT_ESCAPE_BINDING,
        QUIT_Q_BINDING,
        NAV_DOWN_J_BINDING,
        NAV_UP_K_BINDING,
        CONFIRM_ENTER_BINDING,
        CONFIRM_C_BINDING,
    )

    def compose(self) -> ComposeResult:
        """Build the provider selection UI."""
        yield Header()
        with Container(id="provider-container"):
            yield Static("Welcome to Flow GTD", id="welcome-title")
            yield Static(
                "Select your AI provider to get started",
                id="welcome-subtitle",
            )
            with Vertical(id="provider-form"):
                yield Static("Choose Provider", id="provider-label")
                with RadioSet(id="provider-radio"):
                    for i, provider in enumerate(PROVIDERS):
                        # First provider (Gemini) is selected by default
                        yield RadioButton(
                            provider.display_name,
                            id=f"provider-{provider.id}",
                            value=(i == 0),
                        )
                yield Static(
                    PROVIDER_HINTS["gemini"],
                    id="provider-hint",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Focus the radio set on mount."""
        radio_set = self.query_one("#provider-radio", RadioSet)
        radio_set.focus()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Update hint when selection changes."""
        if event.pressed and event.pressed.id:
            provider_id = event.pressed.id.replace("provider-", "")
            hint = PROVIDER_HINTS.get(provider_id, "")
            self.query_one("#provider-hint", Static).update(hint)

    def action_cursor_down(self) -> None:
        """Move selection down."""
        radio_set = self.query_one("#provider-radio", RadioSet)
        radio_set.action_next_button()

    def action_cursor_up(self) -> None:
        """Move selection up."""
        radio_set = self.query_one("#provider-radio", RadioSet)
        radio_set.action_previous_button()

    def action_confirm(self) -> None:
        """Confirm selection and proceed to credentials screen."""
        radio_set = self.query_one("#provider-radio", RadioSet)

        # Get selected provider ID (default to gemini if none selected)
        if radio_set.pressed_button and radio_set.pressed_button.id:
            provider_id = radio_set.pressed_button.id.replace("provider-", "")
        else:
            # Fallback to first provider (gemini)
            provider_id = PROVIDERS[0].id

        # Cast to OnboardingApp for type safety
        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        onboarding_app.selected_provider = provider_id

        # Push credentials screen
        from flow.tui.onboarding.screens.credentials import CredentialsScreen

        self.app.push_screen(CredentialsScreen())

    def action_quit(self) -> None:
        """Exit the application."""
        self.app.exit()
