"""Screen 3: Credential Validation."""

import logging
from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, LoadingIndicator, Static

from flow.tui.onboarding.constants import VALIDATION_PROMPT
from flow.utils.llm.provider import LLMProvider

if TYPE_CHECKING:
    from flow.tui.onboarding.app import OnboardingApp

logger = logging.getLogger(__name__)

# Timeout for validation requests (short for quick feedback)
VALIDATION_TIMEOUT = 10.0


class ValidationScreen(Screen):
    """Validate credentials by testing connection to the LLM provider."""

    CSS_PATH = "validation.tcss"

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("r", "retry", "Retry"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._validation_error: Optional[str] = None
        self._validation_success: bool = False

    def compose(self) -> ComposeResult:
        """Build the validation UI."""
        yield Header()
        with Container(id="validation-container"):
            yield Static("Validating Configuration", id="validation-title")
            yield Static(
                "Testing connection to your LLM provider...", id="validation-subtitle"
            )

            with Vertical(id="validation-status"):
                # Loading state
                with Vertical(id="loading-state"):
                    yield LoadingIndicator(id="loader")
                    yield Static("Connecting...", id="loading-text")

                # Success state
                with Vertical(id="success-state"):
                    yield Static("✓", id="success-icon")
                    yield Static("Connection Successful!", id="success-text")
                    yield Static(
                        "Your configuration has been saved.",
                        id="success-detail",
                    )

                # Error state
                with Vertical(id="error-state"):
                    yield Static("✗", id="error-icon")
                    yield Static("Connection Failed", id="error-text")
                    yield Static("", id="error-detail")

            # Action buttons
            with Horizontal(id="validation-actions"):
                yield Button("Back", id="back-btn")
                yield Button("Retry", id="retry-btn")
                yield Button("Start Flow", id="start-btn", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        """Start validation on mount."""
        self._show_loading()
        self.run_worker(self._validate_credentials(), exclusive=True)

    def _show_loading(self) -> None:
        """Show loading state."""
        self.query_one("#loading-state", Vertical).display = True
        self.query_one("#success-state", Vertical).display = False
        self.query_one("#error-state", Vertical).display = False
        self.query_one("#retry-btn", Button).display = False
        self.query_one("#start-btn", Button).display = False
        self.query_one("#back-btn", Button).display = False

    def _show_success(self) -> None:
        """Show success state."""
        self.query_one("#loading-state", Vertical).display = False
        self.query_one("#success-state", Vertical).display = True
        self.query_one("#error-state", Vertical).display = False
        self.query_one("#retry-btn", Button).display = False
        self.query_one("#start-btn", Button).display = True
        self.query_one("#back-btn", Button).display = False

    def _show_error(self, message: str) -> None:
        """Show error state with message."""
        self.query_one("#loading-state", Vertical).display = False
        self.query_one("#success-state", Vertical).display = False
        self.query_one("#error-state", Vertical).display = True
        self.query_one("#error-detail", Static).update(message)
        self.query_one("#retry-btn", Button).display = True
        self.query_one("#start-btn", Button).display = False
        self.query_one("#back-btn", Button).display = True

    async def _validate_credentials(self) -> None:
        """Validate credentials by sending a test request."""
        import asyncio

        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        provider = onboarding_app.selected_provider
        credentials = onboarding_app.credentials

        try:
            # Short delay to show loading state
            await asyncio.sleep(0.5)

            # Create provider instance with temp credentials
            llm_provider = self._create_provider(provider, credentials)
            if llm_provider is None:
                # Surface the actual error from _create_provider
                error_msg = self._validation_error or "Failed to initialize provider"
                self._show_error(error_msg)
                return

            # Test with a simple ping using the validation prompt
            result = await asyncio.to_thread(
                llm_provider.generate_text,
                VALIDATION_PROMPT,
                None,
                False,  # sanitize=False for short prompt
            )

            if result:
                # Success - save configuration
                self._save_config(provider, credentials)
                self._validation_success = True
                self._show_success()
            else:
                self._show_error("Provider did not respond. Check your credentials.")

        except (OSError, ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            logger.error("Credential validation failed: %s: %s", type(e).__name__, e)
            error_msg = self._format_error(e)
            self._show_error(error_msg)

    def _create_provider(
        self, provider: str, credentials: dict
    ) -> Optional[LLMProvider]:
        """Create a provider instance with given credentials.

        Args:
            provider: Provider ID ("gemini", "openai", "ollama").
            credentials: Provider-specific credentials dict.

        Returns:
            LLMProvider instance or None if creation failed.
        """
        try:
            if provider == "gemini":
                from flow.utils.llm.gemini import GeminiProvider

                return GeminiProvider(
                    api_key=credentials.get("api_key", ""),
                    timeout=VALIDATION_TIMEOUT,
                )
            elif provider == "openai":
                from flow.utils.llm.openai import OpenAIProvider

                return OpenAIProvider(
                    api_key=credentials.get("api_key", ""),
                    timeout=VALIDATION_TIMEOUT,
                )
            elif provider == "ollama":
                from flow.utils.llm.ollama import OllamaProvider

                return OllamaProvider(
                    base_url=credentials.get("base_url", "http://localhost:11434"),
                    timeout=VALIDATION_TIMEOUT,
                )
        except ImportError as e:
            logger.error("Provider import failed: %s", e)
            self._validation_error = f"Missing dependency: {e}"
        except (ValueError, TypeError) as e:
            logger.error("Provider configuration error: %s", e)
            self._validation_error = f"Invalid configuration: {e}"
        return None

    def _save_config(self, provider: str, credentials: dict) -> None:
        """Save validated configuration to file."""
        from flow.utils.llm.config import save_config

        save_config(
            provider=provider,  # type: ignore[arg-type]
            credentials=credentials,
            onboarding_completed=True,
        )

    def _format_error(self, error: Exception) -> str:
        """Format error message for display with actionable guidance.

        Args:
            error: The exception that occurred during validation.

        Returns:
            User-friendly error message with troubleshooting hints.
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # Provide user-friendly messages with actionable guidance for common errors
        if "401" in error_msg or "Unauthorized" in error_msg:
            return (
                "Invalid API key. Please check:\n"
                "  • Key was copied correctly (no extra spaces)\n"
                "  • Key has not expired\n"
                "  • You're using the correct provider's key"
            )
        if "403" in error_msg or "Forbidden" in error_msg:
            return (
                "API key does not have permission. Please check:\n"
                "  • Account billing is set up\n"
                "  • API access is enabled\n"
                "  • Rate limits haven't been exceeded"
            )
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            return (
                "Could not connect to server. Please check:\n"
                "  • URL is correct\n"
                "  • Server is running\n"
                "  • Network/firewall allows connection"
            )
        if "timeout" in error_msg.lower():
            return (
                "Connection timed out. Possible causes:\n"
                "  • Server is slow or overloaded\n"
                "  • Network issues\n"
                "  • Try again in a moment"
            )
        if "ImportError" in error_type:
            return f"Missing dependency. Run: pip install {error_msg}"

        # Fallback to original message
        return f"{error_type}: {error_msg[:100]}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-btn":
            self.action_go_back()
        elif event.button.id == "retry-btn":
            self.action_retry()
        elif event.button.id == "start-btn":
            self._start_flow()

    def action_go_back(self) -> None:
        """Return to credentials screen."""
        self.app.pop_screen()

    def action_retry(self) -> None:
        """Retry validation."""
        self._show_loading()
        self.run_worker(self._validate_credentials(), exclusive=True)

    def _start_flow(self) -> None:
        """Exit onboarding and signal to start main app."""
        self.app.exit(result=True)
