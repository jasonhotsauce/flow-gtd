# Flow GTD

Local-first, AI-augmented GTD as a native macOS app.

## Product

Flow is now a native macOS experience built with SwiftUI. The retired terminal UI is no longer part of the supported product surface.

The current native app includes:

- Today, Inbox, Projects, Review, Assistant, and Memory views in a native split-view shell
- quick capture, clarify, inbox conversion, task/project lifecycle actions, toolbar search, sidebar navigation, and keyboard selection movement
- assistant sessions and messages with explicit proposal contracts, proposal confirmation, audit trail, and local undo for supported assistant-created writes
- inspectable Memory records with search, editing, enable/disable, deletion, and visible rationale
- daily planning with accepted top/bonus tasks, candidate buckets, risk flags, calendar-aware degraded reasoning, and Flow-owned notification policy state
- weekly review packages with completed work, stale items, inbox cleanup candidates, project health, upcoming deadlines, and audited batch cleanup actions
- local SQLite-backed data access with normalized native workflow tables owned by the bundled TypeScript sidecar
- Apple Reminders import plus explicit opt-in write-back with conflict handling
- automatic Flow-owned Apple Calendar event creation/reconciliation for eligible tasks

Deferred from this branch:

- open-ended agent self-improvement
- broad knowledge-base search
- highly customized productivity methodologies beyond the default guided workflow
- autonomous EventKit writes without explicit Flow policy and conflict records

Current status: native PRD workflow implementation is in place for launch-critical capture, clarify, planning, review, assistant, memory, notification policy, Reminders sync, and calendar-event sync. Final verification and release-documentation cleanup are tracked in `tasks/todo.md`.

## Runtime Architecture

The shipped native app now runs against a bundled local TypeScript sidecar.

- `Sources/FlowMacApp/` remains the macOS UI shell.
- `Sources/FlowMacCore/` owns native state, IPC, and Apple bridge adapters.
- `sidecar/` owns the shipped product runtime: SQLite access, GTD reads and writes, assistant sessions and messages, proposal confirmation, audit persistence, undo, and orchestrated specialist routing.
- Legacy assistant turn helpers remain in compatibility paths for review-guidance and migration-era tests, but the product surface is session/message-first.
- Swift continues to host Apple-native integrations such as Reminders, Calendar, and notification capability checks behind a narrow bridge contract.
- Python remains in the repository for legacy support and migration-era tooling, but it is not required for normal native app execution.

Current sidecar scope:

- bundled private Node runtime plus compiled `sidecar/dist` output inside the app bundle
- provider-neutral assistant orchestration with a Codex-backed native assistant path, explicit provider evidence, deterministic fallback, and write-proposal validation
- sidecar-backed workspace snapshot, planning, review, memory, task-state, and assistant session/message mutation flows
- explicit degraded-mode startup/retry UI when the background runtime is unavailable
- Apple bridge capability/status handoff from Swift to the sidecar

Provider targets:

- Codex-backed provider for the shipped native assistant path when the local Codex runtime is available
- deterministic provider for bounded fallback behavior and non-migrated specialist routes
- OpenAI and Anthropic adapter boundaries for future runtime-backed model execution
- the legacy Python Codex CLI adapter is not the shipped native assistant path

## Repository Layout

- `Sources/FlowMacApp/`: SwiftUI app shell and views
- `Sources/FlowMacCore/`: app state, sidecar IPC, repository bridge, and Apple-native integration adapters
- `sidecar/`: shipped TypeScript backend for SQLite access, domain logic, and assistant orchestration
- `flow/`: legacy Python support code retained for migration support and non-shipped tooling
- `scripts/build_native_app.sh`: native app bundle build
- `scripts/test_native_app.sh`: native smoke verification

## Build

Build the app bundle with:

```bash
./scripts/build_native_app.sh
```

The app bundle is emitted at `.build/native/Flow.app` and includes the private Node runtime plus compiled sidecar resources under `Contents/Resources/sidecar-runtime/`.

## Install With Homebrew

Flow ships as a native macOS app through a Homebrew Cask:

```bash
brew tap <github-user>/flow
brew install --cask flow-gtd
open -a "Flow GTD"
```

The Cask installs `Flow.app` from the native release archive. Python is not required for normal app usage.

## Verify

Run native smoke verification with:

```bash
./scripts/test_native_app.sh
```

This repository expects a working macOS toolchain with Xcode command line tools and a compatible SDK.

For sidecar development, install Node dependencies once:

```bash
cd sidecar
npm install
```

## Development Setup

For Python-side development and tests:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip3 install poetry
poetry install
```

Optional extras:

```bash
poetry install --extras "web"
poetry install --extras "rag"
```

## Release

The native release artifact is:

```text
dist/Flow-<version>-macos-<arch>.zip
```

Maintainer release flow:

```bash
source .venv/bin/activate
pytest tests/unit -v
./scripts/test_native_app.sh
make native-release-archive
make release
make brew-cask
```

`make native-release-archive` builds `.build/native/Flow.app`, validates the bundle layout, and packages the app with `ditto`. `make release` requires a clean working tree, creates the GitHub release, and attaches the native zip asset. `make brew-cask` renders the Cask from the uploaded release archive so it can be copied to the tap at `homebrew-flow/Casks/flow-gtd.rb`.

For local tap testing before upload, run `make brew-cask-local` after `make native-release-archive`; it hashes the existing local archive without rebuilding it.

`make release` packages the app unsigned, creates the GitHub release, and attaches the native zip asset. Unsigned builds do not require an Apple Developer account, but macOS may show Gatekeeper trust warnings for users because the app is not Developer ID signed or notarized.

### Automated GitHub Release

Pushing a branch named `release/v<version>` or `release/<version>` runs `.github/workflows/release-native-macos.yml`. The branch version must match `pyproject.toml`, for example `release/v0.8.0` for `version = "0.8.0"`.

The workflow:

- installs Python and Node dependencies
- runs unit and native smoke tests
- builds `.build/native/Flow.app`
- packages the unsigned app archive
- creates the GitHub release with `dist/Flow-<version>-macos-<arch>.zip`
- renders the Cask and commits it to the Homebrew tap over a repository-scoped deploy key

Create a protected GitHub Environment named `release`, restrict it to release branches, and require a reviewer before deployment. Store the Homebrew tap deploy key as an environment secret on that environment, not as a repository file or plain repository variable.

Required `release` environment secrets:

| Secret | Description |
|--------|-------------|
| `HOMEBREW_TAP_DEPLOY_KEY` | Private SSH deploy key with write access only to the Homebrew tap repository |

Optional GitHub variable:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOMEBREW_TAP_REPOSITORY` | `<owner>/homebrew-flow` | Tap repository updated by the workflow |

No Apple Developer ID certificate or App Store Connect API key is required for this unsigned release workflow.

For the complete end-to-end setup, including GitHub Environment configuration and first-party Homebrew update behavior, see `docs/release-automation-setup.md`.

## Configuration

| Variable | Description |
|----------|-------------|
| `FLOW_DB_PATH` | SQLite path (default: `data/flow.db`) |
| `FLOW_LLM_PROVIDER` | LLM provider override (`gemini`, `openai`, `ollama`) |
| `FLOW_AGENT_RUNTIME_PROVIDER` | Agent runtime provider (`deterministic`, `codex`, `openai-agents`, `claude-agent`) |
| `FLOW_AGENT_RUNTIME_MODEL` | Agent runtime model override for providers that use models |
| `FLOW_AGENT_RUNTIME_TIMEOUT` | Agent runtime timeout in seconds |
| `FLOW_GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini API key |
| `FLOW_OPENAI_API_KEY` | OpenAI API key when provider is `openai` |
| `FLOW_OLLAMA_BASE_URL` | Ollama base URL (default: `http://localhost:11434`) |
| `FLOW_RESOURCE_STORAGE` | Resource storage provider (`flow-library`, `obsidian-vault`) |
| `FLOW_OBSIDIAN_VAULT_PATH` | Obsidian vault path when using `obsidian-vault` |
| `FLOW_OBSIDIAN_NOTES_DIR` | Notes subfolder for Flow resources (default: `flow/resources`) |

## Worktrees

If you use the sibling worktree layout with shared parent assets, create a new checkout from the parent directory with:

```bash
../create_worktree.sh <new-worktree-name>
```

To re-bootstrap an existing checkout from the same parent layout:

```bash
make -C main worktree-setup WORKTREE=main
make -C main worktree-setup WORKTREE=<worktree-name>
```

## License

MIT License. See [LICENSE](LICENSE).
