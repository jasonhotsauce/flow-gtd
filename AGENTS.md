# Codex Setup for Flow GTD

This repository is configured for Codex-first collaboration.

## Scope

- Apply these instructions to all files in this repository.
- If instructions conflict, prefer explicit user instructions in the current chat, then this file.

## Worktree Workflow (Mandatory)

- `main/` is the stable checkout and must not be edited unless the user explicitly asks for it.
- Before any new bugfix or feature implementation in this repository, use `.codex/skills/worktree-development/SKILL.md`.
- The required launcher lives in the shared parent directory. From any checkout under that parent, run `../create_worktree.sh <worktree-name>`.
- Keep the current Codex session after launcher execution and point every subsequent read, edit, and test command at the created sibling worktree path only.
- Shared Codex assets live in the parent directory at `../.codex/` and are copied into each worktree as a local `.codex/` runtime directory during bootstrap.

## Shared Codex Runtime

- Expanded workflow guidance lives in:
  - `.codex/docs/agent-workflow.md`
  - `.codex/docs/project-guardrails.md`
  - `.codex/docs/skills-index.md`
- Durable project memory lives under `.codex/memory/`.
- Hooks are configured through `.codex/hooks.json` and assume Codex hooks are enabled in the user config.
- plans should be created in `.codex/plans/`.

## Project Snapshot

- Product: Local-first, AI-augmented GTD CLI for macOS users.
- Core stack: Python 3.11+, `typer`, `textual`, raw `sqlite3`, optional ChromaDB, PyObjC EventKit.
- LLM integration: `flow/utils/llm/` (Gemini, OpenAI, Ollama), config in `~/.flow/config.toml`.

## Non-Negotiable Guardrails

- Always bootstrap and activate the repository virtual environment before running Python scripts:
  - If `.venv` is missing, create it with Python 3.11+:
    - `python3.11 -m venv .venv` (preferred)
    - fallback only if `python3` is already 3.11+
  - Run `source .venv/bin/activate` first in the shell session.
  - Ensure dependency tooling exists in venv:
    - `pip3 install poetry`
  - Install project dependencies:
    - `poetry install` (preferred)
    - `make install` (wrapper target, equivalent for default setup)
  - After activation, use `python` / `pytest` from that active environment.
  - Use Poetry commands when changing dependencies.
- Preserve dependency direction:
  - Presentation (`flow/cli.py`, `flow/tui/`) -> Core (`flow/core/`) -> Models/Database/Sync.
  - `flow/models/` stays pure domain logic.
  - `flow/database/` and `flow/sync/` must not import from `flow/core/`.
- Keep file placement aligned with the existing package layout.

## Quality Bar

- For code changes in `flow/` or `tests/`, bootstrap a new agent and run `.codex/skills/code-review-flow/SKILL.md` to review the changes, only finalize if review passes.
- Run targeted tests for touched behavior when practical:
  - `pytest tests/unit -v`
- Update `README.md` and affected docs in the same task when behavior changes.

## Migration Note

- New agent behavior should be encoded in this `AGENTS.md` plus the shared parent `.codex/` source that is copied into each worktree.
