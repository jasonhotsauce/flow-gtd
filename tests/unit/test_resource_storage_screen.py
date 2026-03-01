"""Unit tests for onboarding resource storage selection screen."""

from __future__ import annotations

from textual._context import active_app

from flow.tui.onboarding.screens.resource_storage import ResourceStorageScreen


class _FakeStorageApp:
    def __init__(self) -> None:
        self.push_calls: list[object] = []
        self.resource_storage: str = "flow-library"
        self.resource_settings: dict[str, str] = {
            "obsidian_vault_path": "",
            "obsidian_notes_dir": "flow/resources",
        }

    def push_screen(self, screen: object) -> None:
        self.push_calls.append(screen)

    def pop_screen(self) -> None:
        return


class _FakeInput:
    def __init__(self, value: str) -> None:
        self.value = value
        self.display = True


class _FakeStatic:
    def __init__(self) -> None:
        self.display = True

    def update(self, _text: str) -> None:
        return


class _FakeRadioButton:
    def __init__(self, button_id: str) -> None:
        self.id = button_id


class _FakeRadioSet:
    def __init__(self, button_id: str) -> None:
        self.pressed_button = _FakeRadioButton(button_id)


def test_resource_storage_confirm_sets_selection_and_pushes_credentials() -> None:
    screen = ResourceStorageScreen()
    fake_app = _FakeStorageApp()

    def fake_query_one(selector: str, _kind: object) -> object:
        if selector == "#storage-radio":
            return _FakeRadioSet("storage-flow-library")
        if selector == "#obsidian-vault-input":
            return _FakeInput("")
        if selector == "#obsidian-folder-input":
            return _FakeInput("flow/resources")
        if selector == "#obsidian-vault-label":
            return _FakeStatic()
        if selector == "#obsidian-folder-label":
            return _FakeStatic()
        if selector == "#storage-hint":
            return _FakeStatic()
        raise AssertionError(f"unexpected selector: {selector}")

    screen.query_one = fake_query_one  # type: ignore[method-assign]

    token = active_app.set(fake_app)  # type: ignore[arg-type]
    try:
        screen.action_confirm()
    finally:
        active_app.reset(token)

    assert fake_app.resource_storage == "flow-library"
    assert len(fake_app.push_calls) == 1
    assert fake_app.push_calls[0].__class__.__name__ == "CredentialsScreen"
