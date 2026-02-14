# Hybrid Defer Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a GTD-aligned defer chooser with three outcomes (`Waiting For`, `Defer Until`, `Someday/Maybe`) for Process Stage 3 and Projects detail flows.

**Architecture:** Keep persistence schema unchanged by storing tickler datetime in `Item.meta_payload["defer_until"]` while using existing statuses for waiting/someday. Centralize defer-mode behavior and active-item filtering in `Engine`, then call that logic from Textual screens through a reusable modal.

**Tech Stack:** Python 3.11+, Textual, sqlite3, Pydantic models, pytest.

---

### Task 1: Add date parsing tests for `Defer Until`

**Files:**
- Create: `tests/unit/test_defer_utils.py`
- Modify: `flow/core/__init__.py`

**Step 1: Write the failing tests**

```python
from datetime import datetime

from flow.core.defer_utils import parse_defer_until


def test_parse_tomorrow_returns_9am_local() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("tomorrow", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-15"
    assert result.hour == 9


def test_parse_next_week_returns_same_weekday_9am() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("next week", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-21"
    assert result.hour == 9


def test_parse_explicit_date() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("2026-02-20", now)
    assert result is not None
    assert result.date().isoformat() == "2026-02-20"
    assert result.hour == 9


def test_parse_explicit_datetime() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    result = parse_defer_until("2026-02-20 13:45", now)
    assert result is not None
    assert result.hour == 13
    assert result.minute == 45


def test_parse_invalid_returns_none() -> None:
    now = datetime(2026, 2, 14, 15, 0)
    assert parse_defer_until("someday maybe", now) is None
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate
pytest tests/unit/test_defer_utils.py -v
```

Expected: FAIL with `ModuleNotFoundError: flow.core.defer_utils`.

**Step 3: Commit**

```bash
git add tests/unit/test_defer_utils.py
git commit -m "test: add defer-until parser coverage"
```

### Task 2: Implement defer date parsing utility

**Files:**
- Create: `flow/core/defer_utils.py`
- Modify: `flow/core/__init__.py`
- Test: `tests/unit/test_defer_utils.py`

**Step 1: Write minimal implementation**

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


DEFAULT_DEFER_HOUR = 9


def parse_defer_until(raw: str, now: Optional[datetime] = None) -> Optional[datetime]:
    value = raw.strip().lower()
    current = now or datetime.now()

    if value == "tomorrow":
        target = current + timedelta(days=1)
        return target.replace(hour=DEFAULT_DEFER_HOUR, minute=0, second=0, microsecond=0)

    if value == "next week":
        target = current + timedelta(days=7)
        return target.replace(hour=DEFAULT_DEFER_HOUR, minute=0, second=0, microsecond=0)

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw.strip(), fmt)
            if fmt == "%Y-%m-%d":
                return parsed.replace(hour=DEFAULT_DEFER_HOUR, minute=0)
            return parsed
        except ValueError:
            continue

    return None
```

**Step 2: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate
pytest tests/unit/test_defer_utils.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add flow/core/defer_utils.py flow/core/__init__.py tests/unit/test_defer_utils.py
git commit -m "feat: add defer-until parser utility"
```

### Task 3: Add engine tests for hybrid defer semantics

**Files:**
- Modify: `tests/unit/test_engine.py`
- Test: `flow/core/engine.py`

**Step 1: Write failing engine tests**

```python
from datetime import datetime, timedelta


def test_defer_waiting_sets_waiting_status(engine: Engine) -> None:
    item = engine.capture("Call vendor")
    engine.defer_item(item.id, mode="waiting")
    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "waiting"


def test_defer_someday_sets_someday_status(engine: Engine) -> None:
    item = engine.capture("Maybe learn SwiftUI")
    engine.defer_item(item.id, mode="someday")
    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "someday"


def test_defer_until_stores_timestamp_and_hides_from_next_actions(engine: Engine) -> None:
    item = engine.capture("Write proposal")
    future = datetime.now() + timedelta(days=2)
    engine.defer_item(item.id, mode="until", defer_until=future)

    updated = engine.get_item(item.id)
    assert updated is not None
    assert updated.status == "active"
    assert "defer_until" in updated.meta_payload

    visible_ids = {it.id for it in engine.next_actions()}
    assert item.id not in visible_ids
```

**Step 2: Run targeted test and confirm fail**

Run:
```bash
source .venv/bin/activate
pytest tests/unit/test_engine.py -v
```

Expected: FAIL because `Engine.defer_item` and filtering behavior are not implemented.

**Step 3: Commit**

```bash
git add tests/unit/test_engine.py
git commit -m "test: define hybrid defer behavior in engine tests"
```

### Task 4: Implement engine defer API and next-action filtering

**Files:**
- Modify: `flow/core/engine.py`
- Test: `tests/unit/test_engine.py`

**Step 1: Implement defer and filtering logic**

```python
from datetime import datetime
from typing import Literal, Optional

DeferMode = Literal["waiting", "until", "someday"]


def _is_defer_until_visible(self, item: Item, now: datetime) -> bool:
    raw = item.meta_payload.get("defer_until")
    if not raw:
        return True
    try:
        until = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    return until <= now


def next_actions(self, parent_id: Optional[str] = None) -> list[Item]:
    items = self._db.list_actions(status="active", parent_id=parent_id)
    now = datetime.now()
    return [item for item in items if self._is_defer_until_visible(item, now)]


def defer_item(
    self,
    item_id: str,
    mode: DeferMode = "waiting",
    defer_until: Optional[datetime] = None,
    note: Optional[str] = None,
) -> None:
    item = self._db.get_item(item_id)
    if not item:
        return

    if mode == "waiting":
        payload = dict(item.meta_payload)
        if note:
            payload["defer_note"] = note
        self._db.update_item(item.model_copy(update={"status": "waiting", "meta_payload": payload}))
        return

    if mode == "someday":
        self._db.update_item(item.model_copy(update={"status": "someday"}))
        return

    if mode == "until" and defer_until is not None:
        payload = dict(item.meta_payload)
        payload["defer_until"] = defer_until.isoformat()
        self._db.update_item(item.model_copy(update={"status": "active", "meta_payload": payload}))
```

Also update `two_min_defer` to call `defer_item` for mode-based behavior.

**Step 2: Run tests and verify pass**

Run:
```bash
source .venv/bin/activate
pytest tests/unit/test_engine.py -v
```

Expected: PASS for new defer tests and existing engine tests.

**Step 3: Commit**

```bash
git add flow/core/engine.py tests/unit/test_engine.py
git commit -m "feat: implement hybrid defer behavior in engine"
```

### Task 5: Add reusable Textual defer chooser modal

**Files:**
- Create: `flow/tui/common/widgets/defer_dialog.py`
- Modify: `flow/tui/common/widgets/__init__.py`

**Step 1: Implement modal screen component**

```python
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option


class DeferDialog(ModalScreen[dict | None]):
    def compose(self) -> ComposeResult:
        yield Static("Choose defer type")
        options = OptionList(
            Option("Waiting For", id="waiting"),
            Option("Defer Until", id="until"),
            Option("Someday/Maybe", id="someday"),
            Option("Cancel", id="cancel"),
            id="defer-options",
        )
        yield options
        yield Input(placeholder="tomorrow | next week | YYYY-MM-DD | YYYY-MM-DD HH:MM", id="defer-until-input")
```

Dialog contract:
- Returns `{"mode": "waiting"}`
- Returns `{"mode": "someday"}`
- Returns `{"mode": "until", "raw": "..."}`
- Returns `None` on cancel

**Step 2: Manual smoke test**

Run:
```bash
source .venv/bin/activate
python -m flow.main
```

Expected: Modal can be opened from wired screens in later tasks and closes without crashing.

**Step 3: Commit**

```bash
git add flow/tui/common/widgets/defer_dialog.py flow/tui/common/widgets/__init__.py
git commit -m "feat: add reusable defer chooser modal"
```

### Task 6: Wire Process Stage 3 defer flow

**Files:**
- Modify: `flow/tui/screens/process/process.py`
- Test: `tests/unit/test_engine.py`

**Step 1: Update defer handler to use modal + engine defer**

Implementation details:
- In `action_defer`, open `DeferDialog` via `self.app.push_screen` callback.
- On result:
  - `waiting`: call `self._engine.defer_item(item.id, mode="waiting")`
  - `someday`: call `self._engine.defer_item(item.id, mode="someday")`
  - `until`: parse `raw` with `parse_defer_until`; show error toast if invalid.
- Always call `two_min_advance()` after a successful defer branch.

**Step 2: Run targeted tests**

Run:
```bash
source .venv/bin/activate
pytest tests/unit/test_engine.py -v
```

Expected: PASS; process defer now relies on tested engine semantics.

**Step 3: Commit**

```bash
git add flow/tui/screens/process/process.py flow/core/defer_utils.py
git commit -m "feat: wire process stage defer chooser"
```

### Task 7: Wire Projects detail defer flow (create files if absent)

**Files:**
- Modify or Create: `flow/tui/screens/projects/project_detail.py`
- Modify or Create: `flow/tui/screens/projects/projects.py`
- Modify or Create: `flow/tui/screens/projects/__init__.py`
- Modify as needed: `flow/cli.py`, `flow/tui/app.py`

**Step 1: Ensure projects screen source exists**

If files are missing in current branch, create minimal project list/detail screens first so defer flow has a valid entry point.

**Step 2: Add defer modal behavior to project detail screen**

- Bind `f` to open `DeferDialog`.
- Map selection to `Engine.defer_item(...)` with same logic as Process stage.
- Refresh project action list after successful defer.
- Show toast on parse failure for invalid `Defer Until` input.

**Step 3: Run smoke test**

Run:
```bash
source .venv/bin/activate
python -m flow.main
```

Expected: In Projects detail, pressing `f` allows all three defer outcomes and updates the list.

**Step 4: Commit**

```bash
git add flow/tui/screens/projects flow/cli.py flow/tui/app.py
git commit -m "feat: add hybrid defer flow to project detail"
```

### Task 8: Update docs and run verification suite

**Files:**
- Modify (or create locally if ignored): `docs/features/projects.md`
- Modify: `docs/plans/2026-02-14-defer-feature-design.md` (if any wording sync needed)

**Step 1: Document defer semantics**
- Add concise section mapping:
  - `Waiting For` -> blocked external dependency
  - `Defer Until` -> tickler resurface
  - `Someday/Maybe` -> low-commitment idea list

**Step 2: Run verification commands**

Run:
```bash
source .venv/bin/activate
pytest tests/unit -v
```

Expected: PASS.

**Step 3: Final commit**

```bash
git add tests/unit flow/core flow/tui/screens/process flow/tui/screens/projects docs/features/projects.md
git commit -m "feat: implement hybrid defer workflow with GTD semantics"
```

## Notes for execution

- Required skills during implementation: `test-driven-development`, `textual-ui`, `testing-flow`, `verification-before-completion`, `code-review-flow`.
- Keep DB schema unchanged for this iteration; store `defer_until` in `meta_payload` only.
- Do not block Textual handlers; keep modal handling and parsing lightweight with user-visible error toasts.
