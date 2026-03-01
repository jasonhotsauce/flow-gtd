# Resource Storage Abstraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace direct SQLite resource coupling with a backend-agnostic `ResourceStore` architecture, add Obsidian as a first-class storage option, and add plain-language storage selection during setup.

**Architecture:** Add a `ResourceStore` contract and provider factory, implement `FlowLibrary` and `ObsidianVault` providers, and migrate CLI/engine/onboarding to resolve and use the configured provider. Preserve existing UX commands while removing direct `ResourceDB` usage from callers.

**Tech Stack:** Python 3.11, Typer, Textual, sqlite3, existing RAG/Chroma path, Obsidian CLI integration.

---

### Task 1: Introduce ResourceStore Contract and Shared Types

**Files:**
- Create: `flow/core/resources/store.py`
- Create: `flow/core/resources/models.py`
- Create: `flow/core/resources/__init__.py`
- Test: `tests/unit/core/test_resource_store_contract.py`

**Step 1: Write the failing test**

```python
from typing import Protocol

from flow.core.resources.store import ResourceStore


def test_resource_store_protocol_has_required_methods() -> None:
    required = [
        "save_resource",
        "get_resource",
        "list_resources",
        "search_by_tags",
        "semantic_search",
        "list_tags",
        "health_check",
    ]
    for name in required:
        assert hasattr(ResourceStore, name)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_resource_store_contract.py -v`
Expected: FAIL with import/module not found.

**Step 3: Write minimal implementation**

```python
from typing import Protocol

class ResourceStore(Protocol):
    ...
```

Add dataclasses/pydantic models for backend-agnostic records in `models.py`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_resource_store_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/core/resources tests/unit/core/test_resource_store_contract.py
git commit -m "feat: add resource store contract and shared models"
```

### Task 2: Build Flow Library Provider (Parity Wrapper)

**Files:**
- Create: `flow/core/resources/providers/flow_library.py`
- Create: `flow/core/resources/providers/__init__.py`
- Modify: `flow/core/rag/service.py`
- Test: `tests/unit/core/test_flow_library_resource_store.py`

**Step 1: Write the failing test**

```python
def test_flow_library_store_search_by_tags_matches_resource_db_behavior() -> None:
    # seed resources via store, then search by tag and assert ordering/non-empty
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_flow_library_resource_store.py -v`
Expected: FAIL because provider does not exist.

**Step 3: Write minimal implementation**

- Wrap current `ResourceDB` methods for save/list/tags.
- Reuse existing semantic indexing/search path via existing RAG service.
- Keep return values in contract model types.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_flow_library_resource_store.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/core/resources/providers flow/core/rag/service.py tests/unit/core/test_flow_library_resource_store.py
git commit -m "feat: add flow library resource store provider"
```

### Task 3: Add Obsidian Vault Provider + CLI Adapter

**Files:**
- Create: `flow/core/resources/providers/obsidian_vault.py`
- Create: `flow/utils/obsidian_cli.py`
- Test: `tests/unit/core/test_obsidian_vault_resource_store.py`
- Test: `tests/unit/utils/test_obsidian_cli.py`

**Step 1: Write the failing tests**

```python
def test_obsidian_provider_save_writes_note_with_frontmatter() -> None:
    ...

def test_obsidian_provider_health_check_fails_when_cli_missing() -> None:
    ...
```

```python
def test_obsidian_cli_builds_expected_command() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_obsidian_vault_resource_store.py tests/unit/utils/test_obsidian_cli.py -v`
Expected: FAIL due to missing modules.

**Step 3: Write minimal implementation**

- Add CLI wrapper with typed command builders and result parsing.
- Persist resource content in Obsidian note format (frontmatter includes tags, type, source, created_at).
- Implement tag and semantic search methods through provider strategy.
- Map provider failures to clear exceptions for CLI/onboarding display.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_obsidian_vault_resource_store.py tests/unit/utils/test_obsidian_cli.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/core/resources/providers/obsidian_vault.py flow/utils/obsidian_cli.py tests/unit/core/test_obsidian_vault_resource_store.py tests/unit/utils/test_obsidian_cli.py
git commit -m "feat: add obsidian vault resource provider"
```

### Task 4: Add Resource Store Factory + Configuration Fields

**Files:**
- Create: `flow/core/resources/factory.py`
- Modify: `flow/utils/llm/config.py`
- Test: `tests/unit/core/test_resource_store_factory.py`
- Test: `tests/unit/utils/llm/test_config.py`

**Step 1: Write the failing tests**

```python
def test_factory_builds_obsidian_store_when_resource_storage_is_obsidian() -> None:
    ...

def test_load_config_reads_resource_storage_settings() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_resource_store_factory.py tests/unit/utils/llm/test_config.py -v`
Expected: FAIL because factory and config fields are missing.

**Step 3: Write minimal implementation**

- Add config fields for user-facing storage choice mapping.
- Parse and persist storage settings in config read/write paths.
- Implement factory resolution with actionable error messages.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/core/test_resource_store_factory.py tests/unit/utils/llm/test_config.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/core/resources/factory.py flow/utils/llm/config.py tests/unit/core/test_resource_store_factory.py tests/unit/utils/llm/test_config.py
git commit -m "feat: add resource store factory and config support"
```

### Task 5: Migrate Engine to Store Abstraction

**Files:**
- Modify: `flow/core/engine.py`
- Modify: `flow/core/services/resources.py`
- Test: `tests/unit/test_engine_resources.py`
- Test: `tests/unit/test_engine.py`

**Step 1: Write the failing test**

```python
def test_engine_uses_resource_store_for_tag_and_semantic_lookup(monkeypatch) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_engine_resources.py tests/unit/test_engine.py -v`
Expected: FAIL due to old `ResourceDB`/`RAGService` coupling.

**Step 3: Write minimal implementation**

- Inject/construct `ResourceStore` via factory in engine init.
- Route resource and semantic methods to store.
- Keep method signatures stable for TUI callers.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_engine_resources.py tests/unit/test_engine.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/core/engine.py flow/core/services/resources.py tests/unit/test_engine_resources.py tests/unit/test_engine.py
git commit -m "refactor: route engine resource access through resource store"
```

### Task 6: Migrate CLI save/resources/tags to Store Interface

**Files:**
- Modify: `flow/cli.py`
- Test: `tests/unit/test_cli_main.py`

**Step 1: Write the failing tests**

```python
def test_save_uses_selected_resource_store(monkeypatch) -> None:
    ...

def test_resources_command_reads_from_resource_store(monkeypatch) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_cli_main.py -v`
Expected: FAIL because CLI still instantiates `ResourceDB` directly.

**Step 3: Write minimal implementation**

- Replace direct `ResourceDB` usage with store resolved by config/factory.
- Preserve current command behavior/messages where applicable.
- Remove direct index worker kickoff from CLI command path if provider handles indexing internally.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_cli_main.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/cli.py tests/unit/test_cli_main.py
git commit -m "refactor: migrate cli resource commands to store abstraction"
```

### Task 7: Add Setup/Onboarding Storage Choice (Plain Language)

**Files:**
- Modify: `flow/tui/onboarding/app.py`
- Modify: `flow/tui/onboarding/screens/provider.py`
- Modify: `flow/tui/onboarding/screens/credentials.py`
- Modify: `flow/tui/onboarding/screens/validation.py`
- Create: `flow/tui/onboarding/screens/resource_storage.py`
- Modify: `flow/tui/onboarding/constants.py`
- Test: `tests/unit/test_validation_screen.py`
- Test: `tests/unit/test_onboarding_keybindings_contract.py`
- Create: `tests/unit/test_resource_storage_screen.py`

**Step 1: Write the failing tests**

```python
def test_onboarding_persists_storage_choice_and_obsidian_settings() -> None:
    ...

def test_existing_user_gets_storage_choice_prompt_when_unset() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_validation_screen.py tests/unit/test_onboarding_keybindings_contract.py tests/unit/test_resource_storage_screen.py -v`
Expected: FAIL because storage screen/fields are missing.

**Step 3: Write minimal implementation**

- Add a storage selection screen with user-friendly labels.
- Add Obsidian-specific validation inputs (vault path, optional folder).
- Persist storage choice through config save path.
- Ensure existing users are prompted once when storage choice is absent.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_validation_screen.py tests/unit/test_onboarding_keybindings_contract.py tests/unit/test_resource_storage_screen.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/onboarding tests/unit/test_validation_screen.py tests/unit/test_onboarding_keybindings_contract.py tests/unit/test_resource_storage_screen.py
git commit -m "feat: add onboarding resource storage selection"
```

### Task 8: Documentation + End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/features/projects.md` (or relevant feature doc)
- Modify: `docs/patterns-and-lessons.md` (if storage behavior changes need codified pattern)

**Step 1: Write/adjust failing doc checks (if available)**

If no doc lint exists, proceed to update docs with implementation-accurate instructions.

**Step 2: Run verification suite**

Run:

```bash
source .venv/bin/activate
pytest tests/unit/test_cli_main.py tests/unit/test_engine_resources.py tests/unit/test_validation_screen.py tests/unit/utils/llm/test_config.py -v
pytest tests/unit -v
```

Expected: PASS.

**Step 3: Run required review checklist**

- Execute `.codex/skills/code-review-flow/SKILL.md` checklist against touched `flow/` and `tests/` files.
- Verify security/privacy, architecture placement, typing, async safety, and tests are all satisfied.

**Step 4: Commit docs + final polish**

```bash
git add README.md docs/features docs/patterns-and-lessons.md
git commit -m "docs: document resource storage options and setup"
```

**Step 5: Final validation record**

Capture and include in PR/task summary:

- Commands run
- Pass/fail outcomes
- Any known limitations (for example Obsidian CLI version assumptions)

## Implementation Notes

- Follow @test-driven-development for each task sequence.
- Run @verification-before-completion before claiming success.
- Request review using @requesting-code-review before merge.
