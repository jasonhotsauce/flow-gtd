"""Screen: Resource storage selection for onboarding."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RadioButton, RadioSet, Static

from flow.tui.common.base_screen import FlowScreen
from flow.tui.onboarding.constants import RESOURCE_STORAGE_OPTIONS
from flow.tui.onboarding.keybindings import (
    BACK_ESCAPE_BINDING,
    CONFIRM_C_BINDING,
    CONFIRM_ENTER_BINDING,
    NAV_DOWN_J_BINDING,
    NAV_UP_K_BINDING,
    compose_bindings,
)

if TYPE_CHECKING:
    from flow.tui.onboarding.app import OnboardingApp


class ResourceStorageScreen(FlowScreen):
    """Select resource storage backend with user-friendly labels."""

    CSS_PATH = ["../../common/ops_tokens.tcss", "resource_storage.tcss"]

    BINDINGS = compose_bindings(
        BACK_ESCAPE_BINDING,
        NAV_DOWN_J_BINDING,
        NAV_UP_K_BINDING,
        CONFIRM_ENTER_BINDING,
        CONFIRM_C_BINDING,
    )

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="onboarding-shell"):
            yield Static("Step 2/5  |  Resource Storage", id="onboarding-progress")
            with Horizontal(id="onboarding-layout"):
                with Vertical(id="onboarding-main-pane"):
                    yield Static("Resource Storage", id="onboarding-title")
                    yield Static(
                        "Choose where captured resources are stored.",
                        id="storage-subtitle",
                    )
                    with Vertical(id="storage-form", classes="onboarding-panel"):
                        yield Static("Storage mode", id="storage-title", classes="section-title")
                        with RadioSet(id="storage-radio"):
                            for idx, option in enumerate(RESOURCE_STORAGE_OPTIONS):
                                yield RadioButton(
                                    option.display_name,
                                    id=f"storage-{option.id}",
                                    value=(idx == 0),
                                )

                        yield Static("Obsidian Vault Path", id="obsidian-vault-label")
                        yield Input(
                            placeholder="/Users/you/Documents/MyVault",
                            id="obsidian-vault-input",
                        )

                        yield Static(
                            "Obsidian Notes Folder (optional)", id="obsidian-folder-label"
                        )
                        yield Input(value="flow/resources", id="obsidian-folder-input")
                with Vertical(id="onboarding-ops-pane"):
                    with Vertical(classes="onboarding-side-panel"):
                        yield Static("DETAILS", classes="section-title")
                        yield Static(RESOURCE_STORAGE_OPTIONS[0].hint, id="storage-hint")
        yield Footer()

    def on_mount(self) -> None:
        radio_set = self.query_one("#storage-radio", RadioSet)
        radio_set.focus()
        self._update_obsidian_fields("flow-library")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if not event.pressed or not event.pressed.id:
            return
        option_id = event.pressed.id.replace("storage-", "")
        hint = next((o.hint for o in RESOURCE_STORAGE_OPTIONS if o.id == option_id), "")
        self.query_one("#storage-hint", Static).update(hint)
        self._update_obsidian_fields(option_id)

    def action_cursor_down(self) -> None:
        self.query_one("#storage-radio", RadioSet).action_next_button()

    def action_cursor_up(self) -> None:
        self.query_one("#storage-radio", RadioSet).action_previous_button()

    def action_confirm(self) -> None:
        radio_set = self.query_one("#storage-radio", RadioSet)
        selected = radio_set.pressed_button.id.replace("storage-", "") if radio_set.pressed_button and radio_set.pressed_button.id else "flow-library"

        onboarding_app: OnboardingApp = self.app  # type: ignore[assignment]
        onboarding_app.resource_storage = selected
        onboarding_app.resource_settings = {
            "obsidian_vault_path": self.query_one("#obsidian-vault-input", Input).value.strip(),
            "obsidian_notes_dir": self.query_one("#obsidian-folder-input", Input).value.strip() or "flow/resources",
        }

        if selected == "obsidian-vault" and not onboarding_app.resource_settings["obsidian_vault_path"]:
            self.notify("Please enter your Obsidian vault path", severity="error")
            return

        from flow.tui.onboarding.screens.credentials import CredentialsScreen

        self.app.push_screen(CredentialsScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _update_obsidian_fields(self, selected_id: str) -> None:
        show_obsidian = selected_id == "obsidian-vault"
        self.query_one("#obsidian-vault-label", Static).display = show_obsidian
        self.query_one("#obsidian-vault-input", Input).display = show_obsidian
        self.query_one("#obsidian-folder-label", Static).display = show_obsidian
        self.query_one("#obsidian-folder-input", Input).display = show_obsidian
