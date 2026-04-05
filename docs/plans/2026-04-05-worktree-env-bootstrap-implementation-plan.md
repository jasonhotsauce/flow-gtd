# Worktree Environment Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repo-managed bootstrap command that creates a local `.venv` for `main` or a sibling worktree using dependency files from `main`, plus a parent-root convenience wrapper.

**Architecture:** Keep the real setup logic in a versioned shell script under `main/scripts/`, expose it through `make worktree-setup`, and add a thin wrapper script in the shared parent directory that forwards to the Make target. Test the shell script with temporary directories and stub executables so path resolution and install commands are verified without depending on live package downloads.

**Tech Stack:** GNU Make, POSIX shell, Python `pytest`, `venv`, Poetry

---

### Task 1: Add the failing script test

**Files:**
- Create: `tests/unit/test_worktree_env_setup.py`
- Test: `tests/unit/test_worktree_env_setup.py`

**Step 1: Write the failing test**

Add tests that create a temporary parent directory with:

- `main/pyproject.toml`
- `main/poetry.lock`
- `main/scripts/setup_worktree_env.sh`
- an optional sibling worktree directory
- stub `python3.11` and `python3` executables on `PATH`

The test should assert that:

- running the script for `WORKTREE=feature-x` creates `feature-x/.venv`
- the install step uses `main/pyproject.toml` and `main/poetry.lock`
- running the script for a missing target exits non-zero

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_worktree_env_setup.py -v`

Expected: FAIL because the setup script and Make target do not exist yet.

### Task 2: Implement the bootstrap script

**Files:**
- Create: `scripts/setup_worktree_env.sh`
- Modify: `Makefile`

**Step 1: Write minimal implementation**

Implement a shell script that:

- resolves the parent directory around `main/`
- validates `main/pyproject.toml` and `main/poetry.lock`
- validates the target checkout
- creates target `.venv` with Python 3.11
- installs `poetry` into the target `.venv` if missing
- installs dependencies into the target `.venv` using `main` dependency files

Add a `worktree-setup` Make target that requires `WORKTREE` and invokes the script.

**Step 2: Run the targeted test**

Run: `source .venv/bin/activate && pytest tests/unit/test_worktree_env_setup.py -v`

Expected: PASS

### Task 3: Document the workflow

**Files:**
- Modify: `README.md`
- Modify: `tasks/todo.md`

**Step 1: Update docs**

Document:

- `make -C main worktree-setup WORKTREE=<name>`
- the meaning of `WORKTREE=main`
- that sibling worktrees install from `main` dependencies

**Step 2: Update task tracking**

Mark checklist items complete and record verification results in `tasks/todo.md`.

### Task 4: Add the parent-root convenience wrapper

**Files:**
- Create outside repo checkout: `<parent>/worktree-setup`

**Step 1: Create wrapper**

Create a thin executable wrapper in the parent directory that runs:

```bash
make -C main worktree-setup WORKTREE="$1"
```

**Step 2: Verify wrapper**

Run it once against `main` or the current worktree and confirm it reaches the Make target.

### Task 5: Verify end-to-end behavior

**Files:**
- Verify in: `main/.venv`
- Verify in: `<current-worktree>/.venv`

**Step 1: Run automated verification**

Run: `source .venv/bin/activate && pytest tests/unit/test_worktree_env_setup.py -v`

Expected: PASS

**Step 2: Run real setup commands**

Run from the parent directory:

```bash
make -C main worktree-setup WORKTREE=main
make -C main worktree-setup WORKTREE=project-tasks-as-candidate
./worktree-setup project-tasks-as-candidate
```

Expected:

- `main/.venv` exists
- `project-tasks-as-candidate/.venv` exists
- output clearly identifies target and source checkouts

**Step 3: Record results**

Capture the command outcomes in `tasks/todo.md`.
