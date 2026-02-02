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
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.dark: bool = True
        # Shared state across screens
        self.selected_provider: str = "gemini"
        self.credentials: dict = {}

    def on_mount(self) -> None:
        """Push the first screen on mount."""
        self.push_screen(ProviderSelectScreen())
