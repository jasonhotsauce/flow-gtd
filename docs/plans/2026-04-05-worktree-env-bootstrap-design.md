# Worktree Environment Bootstrap Design

## Goal

Provide a repo-managed way to initialize Python environments for `main/` and sibling git worktrees from the shared parent directory, while keeping `../main` as the dependency source of truth.

## Context

This repository is used through a bare-repo + sibling-worktree layout:

- Parent directory contains `main/` and one or more sibling worktree folders.
- New worktrees should get their own local `.venv`.
- Dependency installation for a new worktree should use the current requirements from `main/`.
- The user wants a convenient command that can be launched from the parent directory, not only from inside a checkout.

## Recommended Design

Use a two-layer setup:

1. Versioned repo-managed setup in `main/`
2. A thin convenience wrapper in the parent directory

### Repo-managed layer

Add a `make worktree-setup` target in `main/Makefile` that calls a versioned script in `main/scripts/setup_worktree_env.sh`.

The script:

- Accepts a target checkout name such as `main` or `project-tasks-as-candidate`
- Resolves the parent directory that contains all worktrees
- Resolves `main/` as the dependency source checkout
- Resolves the target checkout directory from the provided name
- Creates a local `.venv` in the target checkout if missing
- Installs `poetry` into that target `.venv` if needed
- Runs dependency installation for the target checkout using `main/pyproject.toml` and `main/poetry.lock`

This keeps the real logic versioned with the repo and easy to evolve.

### Parent-root convenience layer

Add a small wrapper script in the parent directory that forwards to:

```bash
make -C main worktree-setup WORKTREE=<name>
```

This keeps the convenient entrypoint in the shared worktree root while keeping all real behavior versioned inside `main/`.

## Behavior Details

### Target selection

- `WORKTREE=main` initializes `main/.venv`
- `WORKTREE=<sibling>` initializes `<sibling>/.venv`

### Dependency source

- `main/pyproject.toml` and `main/poetry.lock` are always the install source of truth
- Worktree-local dependency files are not used for initial bootstrap

### Installation path

The install should materialize packages into the target checkout's `.venv`, not into a shared environment.

### Idempotence

Re-running setup should:

- Reuse an existing `.venv`
- Reinstall or refresh dependencies cleanly
- Print clear status about source and target paths

## Failure Handling

Fail fast if:

- The script is not launched from a valid parent directory containing `main/`
- `main/pyproject.toml` or `main/poetry.lock` is missing
- The requested target checkout does not exist
- Python 3.11 is unavailable

## Testing Strategy

Add automated tests for the script behavior using temporary directories and stub executables so the tests validate:

- Target path resolution
- Use of `main` dependency files as the source of truth
- Creation flow for both `main` and sibling worktrees
- Failure behavior for missing targets

Then run one real command against `main` and one against the current worktree to verify the intended workflow.
