"""Onboarding TUI App for first-run experience.

Guides users through LLM provider selection and credential configuration.
"""

from textual.app import App

from flow.tui.onboarding.screens.provider import ProviderSelectScreen


class OnboardingApp(App):
    """Onboarding wizard for Flow GTD.

    A focused wizard that guides new users through:
    1. LLM provider selection (Gemini, OpenAI, Ollama)
    2. Credential entry (API key or server URL)
    3. Connection validation
    """

    CSS_PATH = "../common/theme.tcss"
    TITLE = "Flow GTD Setup"
    SUB_TITLE = "Welcome to Flow"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # Shared state across screens
        self.selected_provider: str = "gemini"
        self.credentials: dict[str, str] = {}
        self.first_capture_outcome: dict[str, str] | None = None

    def on_mount(self) -> None:
        """Push the first screen on mount."""
        self.push_screen(ProviderSelectScreen())

    def get_onboarding_result(self) -> dict[str, object]:
        """Return structured onboarding outcome for follow-up steps."""
        return {
            "completed": True,
            "provider": self.selected_provider,
            "first_capture": self.first_capture_outcome,
        }
