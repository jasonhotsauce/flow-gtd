# Flow: Patterns and Lessons (Cursor Rules)

This doc captures implementation patterns and lessons learned so Cursor and developers can follow consistent rules when changing `flow/` or `tests/`.

---

## 1. CLI vs process lifetime: background work

### Rule

**When a CLI command starts background work (e.g. daemon thread) and then exits, the process exits and daemon threads are terminated before they can finish.** Any work that must be visible or persisted after the command exits must complete before the CLI process exits.

### Lesson (auto-tagging)

- Auto-tagging for `flow c` / `flow capture` was implemented in a **daemon thread**. The CLI printed "Captured: …" and exited; the daemon thread was killed, so:
  - Task `context_tags` were never updated.
  - `increment_tag_usage()` never ran, so `flow tags` (which reads the resources `tags` table) showed no new tags.
- **Fix:** For CLI-invoked capture, run auto-tagging **synchronously** so it finishes before the process exits. The Engine exposes a `block_auto_tag=True` option; the CLI uses it so tags are written before exit.

### Pattern to follow

- If a **CLI command** triggers work that must be visible after the command (e.g. DB updates, tag creation), that work must either:
  - Run in the **same thread** (block until done), or
  - Be deferred to a **long-lived process** (e.g. TUI or a daemon), not a short-lived CLI process.
- Prefer an explicit **block / run-in-foreground** parameter (e.g. `block_auto_tag`) when the same operation can be called from both CLI (short-lived) and TUI (long-lived), so the caller can choose.

---

## 2. Tag visibility: tasks vs `flow tags`

### Rule

- **Task tags** live on the item as `context_tags` (items table).
- **`flow tags`** lists the **tag vocabulary** from the **resources** DB (`tags` table), with usage counts.
- For a tag to appear in `flow tags`, it must be recorded via `ResourceDB.increment_tag_usage(tag)` (and when removing usage, `decrement_tag_usage` where applicable).

So: any feature that adds tags to **tasks** (e.g. auto-tagging on capture) must also call `increment_tag_usage` for each new tag so the tag vocabulary stays in sync and `flow tags` shows them.

---

## 3. Code review requirement

**All changes under `flow/` or `tests/` must pass the project code reviewer** before being considered complete. See:

- `.cursor/rules/code-review-required.mdc` — when review is required.
- `.cursor/agents/code-reviewer.md` — checklist (security, architecture, code quality, Flow-specific rules).

Run `git diff` on modified files and apply that checklist (or invoke the code-reviewer agent) before finalizing.

---

## 4. Quick reference: where things live

| Concern              | Location / pattern |
|----------------------|--------------------|
| CLI capture          | `flow/cli.py` → `_do_capture()` → `Engine.capture(..., block_auto_tag=True)` |
| Capture + auto-tag   | `flow/core/engine.py`: `capture()`, `_run_auto_tagging()`, `_schedule_auto_tagging(..., block=...)` |
| Tag extraction (LLM)| `flow/core/tagging.py`: `extract_tags()` |
| Task tags storage    | Item `context_tags`; persisted in `flow/database/sqlite.py` (items table) |
| Tag vocabulary       | `flow/database/resources.py`: `tags` table, `increment_tag_usage()`, `list_tags()` |
| `flow tags` command  | `flow/cli.py`: `list_tags()` → `ResourceDB.list_tags()` |

---

## 5. Debugging Rules to Prevent Thrash

These rules are mandatory for future bugfix work:

1. **No fixes before evidence**
- Reproduce the bug first.
- Add logs/traces at boundaries and identify where behavior diverges.

2. **One hypothesis, one change**
- Make one minimal change per hypothesis.
- Re-run targeted tests after each change.

3. **Verify framework API contracts early**
- Confirm method signatures/semantics in the installed library before implementation changes.

4. **No time-based masking**
- Do not use arbitrary delays as control flow fixes.
- Prefer deterministic checks based on state and explicit user intent.

5. **Failing regression test first**
- Add a reproducing test before implementing.
- Ensure it fails for the expected reason, then make it pass.

6. **Temporary instrumentation only**
- Remove debug-only probes/log statements after root cause is confirmed and fix is verified.

7. **Reset after repeated misses**
- After two failed fix attempts, stop and return to root-cause investigation.
- Re-document evidence and hypothesis before continuing.
