"""Screen 2: Credentials Entry Form."""

import logging
import webbrowser
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from flow.tui.onboarding.constants import PROVIDER_MAP
from flow.tui.onboarding.keybindings import (
    BACK_CTRL_B_BINDING,
    BACK_ESCAPE_BINDING,
    SUBMIT_ENTER_BINDING,
    compose_bindings,
)

if TYPE_CHECKING:
    from flow.tui.onboarding.app import OnboardingApp

logger = logging.getLogger(__name__)


class CredentialsScreen(Screen):
    """Enter credentials for the selected LLM provider."""

    CSS_PATH = "credentials.tcss"

    BINDINGS = compose_bindings(
        BACK_ESCAPE_BINDING,
        BACK_CTRL_B_BINDING,
        SUBMIT_ENTER_BINDING,
    )

    def compose(self) -> ComposeResult:
        """Build the credentials form UI."""
        yield Header()
        with Container(id="credentials-container"):
            yield Static("Configure Provider", id="creds-title")
            yield Static("", id="creds-subtitle")

            with Vertical(id="credentials-form"):
                # API Key form (for Gemini/OpenAI)
                with Vertical(id="api-key-section"):
                    yield Static("API Key", id="api-key-label")
                    yield Input(
                        placeholder="Paste your API key here...",
                        password=True,
                        id="api-key-input",
                    )
                    with Horizontal(id="api-key-actions"):
                        yield Button("Get API Key", id="get-key-btn", variant="default")
                        yield Static(
                            "Opens browser to provider dashboard",
                            id="get-key-hint",
                        )

                # URL form (for Ollama)
                with Vertical(id="url-section"):
                    yield Static("Server URL", id="url-label")
                    yield Input(
                        value="http://localhost:11434",
                        placeholder="http://localhost:11434",
                        id="url-input",
                    )
                    yield Static(
                        "Make sure Ollama is running locally",
                        id="url-hint",
                    )

                # Action buttons
                with Horizontal(id="form-actions"):
                    yield Button("Back", id="back-btn")
                    yield Button("Continue", id="continue-btn", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        """Configure form based on selected provider."""
        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        provider = onboarding_app.selected_provider
        provider_meta = PROVIDER_MAP.get(provider)
        provider_name = provider_meta.display_name if provider_meta else "Unknown"

        # Update title
        self.query_one("#creds-subtitle", Static).update(
            f"Enter credentials for {provider_name}"
        )

        # Show/hide appropriate sections
        api_key_section = self.query_one("#api-key-section", Vertical)
        url_section = self.query_one("#url-section", Vertical)

        if provider == "ollama":
            api_key_section.display = False
            url_section.display = True
            self.query_one("#url-input", Input).focus()
        else:
            api_key_section.display = True
            url_section.display = False
            self.query_one("#api-key-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "get-key-btn":
            self._open_api_key_url()
        elif event.button.id == "back-btn":
            self.action_go_back()
        elif event.button.id == "continue-btn":
            self.action_submit()

    def _open_api_key_url(self) -> None:
        """Open browser to get API key.

        Validates URL scheme before opening to prevent security issues.
        """
        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        provider = onboarding_app.selected_provider
        provider_meta = PROVIDER_MAP.get(provider)
        if provider_meta and provider_meta.api_key_url:
            url = provider_meta.api_key_url

            # Validate URL scheme to prevent malicious URLs
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                logger.warning("Invalid URL scheme rejected: %s", url)
                self.notify("Invalid URL scheme", severity="error")
                return
            if not parsed.netloc:
                logger.warning("Invalid URL (no host) rejected: %s", url)
                self.notify("Invalid URL", severity="error")
                return

            try:
                webbrowser.open(url)
                self.notify(f"Opening {url} in browser...", timeout=3)
            except (OSError, webbrowser.Error) as e:
                # Browser unavailable (headless, SSH session, etc.)
                logger.debug("Could not open browser: %s", e)
                self.notify(
                    f"Could not open browser. Visit: {url}",
                    severity="warning",
                    timeout=5,
                )

    def action_go_back(self) -> None:
        """Return to provider selection."""
        self.app.pop_screen()

    def action_submit(self) -> None:
        """Validate input and proceed to validation screen."""
        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        provider = onboarding_app.selected_provider

        if provider == "ollama":
            url_input = self.query_one("#url-input", Input)
            url = url_input.value.strip()
            if not url:
                self.notify("Please enter a server URL", severity="error")
                return
            if not url.startswith(("http://", "https://")):
                self.notify("URL must start with http:// or https://", severity="error")
                return
            onboarding_app.credentials = {"base_url": url}
        else:
            api_key_input = self.query_one("#api-key-input", Input)
            api_key = api_key_input.value.strip()
            if not api_key:
                self.notify("Please enter an API key", severity="error")
                return
            onboarding_app.credentials = {"api_key": api_key}

        # Push validation screen
        from flow.tui.onboarding.screens.validation import ValidationScreen

        self.app.push_screen(ValidationScreen())
