# Agent Runtime SDK Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Flow-owned agent runtime foundation, pilot it in assistant fallback responses, and document the gradual migration path from legacy LLM completions to orchestrated agents.

**Architecture:** Introduce `flow/agents/` contracts plus a runtime/adapter boundary while preserving `flow.utils.llm.complete*`. Use a deterministic adapter for the first runtime slice and lazy optional adapter shells for OpenAI Agents SDK, Claude Agent SDK, and Codex CLI. Integrate assistant fallback through the runtime without changing write-capable proposal behavior yet.

**Tech Stack:** Python 3.11, Pydantic, raw sqlite persistence via existing assistant models, pytest, Swift native smoke scripts

## Current Resume Snapshot

This plan is no longer at the initial foundation stage.

Completed in this worktree:
- runtime contracts, deterministic runtime, optional adapter shells
- mocked real OpenAI Agents SDK adapter path with engine/config wiring and lockfile update
- specialist schema layer and shared verifier rules
- runtime-backed read-heavy assistant routes for `daily_plan`, `review`, and read-only `project_health`

Verified in this worktree:
- targeted runtime/assistant/schema tests
- `pytest tests/unit -v` passed: 220 tests
- `./scripts/test_native_app.sh` passed

Resume from:
1. extend `review` into a proposal-producing route with one contract-compatible action
2. extend `project_health` into bounded proposal output
3. keep `capture` and `memory` on the current explicit assistant proposal path until those two write shapes are stable

Important boundary:
- the native Swift assistant path still has parallel logic; current runtime-backed route work is validated on the Python assistant path first

---

### Task 1: Track the new agent runtime migration

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Append checklist**

Add an "Agent Runtime SDK Migration" section with checkboxes for contracts, runtime, config, assistant pilot, docs, review, and verification.

**Step 2: Record migration boundaries**

Include explicit notes that legacy `complete*` stays during Phase 0 and that write-capable assistant routes migrate only after proposal contract tests exist.

**Step 3: Commit**

Run:
```bash
git add tasks/todo.md
git commit -m "chore: track agent runtime migration"
```

Expected:
- Commit succeeds if `tasks/todo.md` is tracked. If `tasks/` is ignored and untracked, leave it local and continue.

### Task 2: Add Flow agent contracts with tests

**Files:**
- Create: `flow/agents/__init__.py`
- Create: `flow/agents/contracts.py`
- Create: `tests/unit/test_agent_runtime_contracts.py`

**Step 1: Write failing tests**

Create tests for:

```python
def test_agent_request_defaults_to_safe_read_only_capabilities() -> None: ...
def test_agent_result_rejects_write_proposal_without_confirmation() -> None: ...
def test_write_proposal_converts_to_assistant_agent_contract_payload() -> None: ...
def test_trace_event_serializes_without_sensitive_raw_prompt() -> None: ...
```

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_agent_runtime_contracts.py -v
```

Expected:
- FAIL because `flow.agents` does not exist yet.

**Step 2: Implement minimal contracts**

Use Pydantic models and literals:

- `AgentCapability`
- `AgentRequest`
- `AgentTraceEvent`
- `AgentWriteProposal`
- `AgentResult`

`AgentWriteProposal.to_agent_contract_payload()` should produce the fields required by `AssistantAgentContract`.

**Step 3: Verify green**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_agent_runtime_contracts.py -v
```

Expected:
- PASS.

**Step 4: Commit**

```bash
git add flow/agents/__init__.py flow/agents/contracts.py tests/unit/test_agent_runtime_contracts.py
git commit -m "feat: add flow agent runtime contracts"
```

### Task 3: Add runtime and deterministic adapter

**Files:**
- Create: `flow/agents/runtime.py`
- Create: `flow/agents/adapters/__init__.py`
- Create: `flow/agents/adapters/base.py`
- Create: `flow/agents/adapters/deterministic.py`
- Create: `tests/unit/test_agent_runtime.py`

**Step 1: Write failing tests**

Create tests for:

```python
def test_runtime_runs_deterministic_adapter_and_records_trace() -> None: ...
def test_runtime_wraps_adapter_error_as_safe_result() -> None: ...
def test_runtime_rejects_adapter_write_without_confirmed_contract() -> None: ...
```

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_agent_runtime.py -v
```

Expected:
- FAIL because runtime files do not exist.

**Step 2: Implement minimal runtime**

- `AgentRuntimeAdapter` protocol with `name` and `run`.
- `AgentRuntime` with `run(request)`.
- `DeterministicAgentAdapter` for local/test responses.
- Safe failure result with no raw exception payload.

**Step 3: Verify green**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_agent_runtime.py -v
```

Expected:
- PASS.

**Step 4: Commit**

```bash
git add flow/agents/runtime.py flow/agents/adapters tests/unit/test_agent_runtime.py
git commit -m "feat: add deterministic agent runtime"
```

### Task 4: Add config fields and optional adapter shells

**Files:**
- Modify: `flow/utils/llm/config.py`
- Modify: `tests/unit/utils/llm/test_config.py`
- Create: `flow/agents/adapters/openai_agents.py`
- Create: `flow/agents/adapters/claude_agent.py`
- Create: `flow/agents/adapters/codex_cli.py`
- Create: `tests/unit/test_agent_adapter_imports.py`

**Step 1: Write failing tests**

Test:

- `load_config` reads `[agents] runtime_provider = "openai-agents"`.
- env override `FLOW_AGENT_RUNTIME_PROVIDER` works.
- invalid provider falls back to `"deterministic"`.
- importing adapter shells does not require `openai-agents`, `claude-agent-sdk`, or Codex CLI installed.

Run:
```bash
source .venv/bin/activate && pytest tests/unit/utils/llm/test_config.py tests/unit/test_agent_adapter_imports.py -v
```

Expected:
- FAIL on missing config fields and files.

**Step 2: Implement config and shells**

- Add `AgentRuntimeProviderType` literal.
- Add `AgentRuntimeConfig`.
- Add `agent_runtime` to `LLMConfig`.
- Implement lazy adapter shells that raise clear unavailable errors only when instantiated/run.

**Step 3: Verify green**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/utils/llm/test_config.py tests/unit/test_agent_adapter_imports.py -v
```

Expected:
- PASS.

**Step 4: Commit**

```bash
git add flow/utils/llm/config.py flow/agents/adapters tests/unit/utils/llm/test_config.py tests/unit/test_agent_adapter_imports.py
git commit -m "feat: configure optional agent runtime adapters"
```

### Task 5: Pilot assistant fallback through runtime

**Files:**
- Modify: `flow/core/services/assistant.py`
- Modify: `flow/core/engine.py`
- Modify: `tests/unit/test_assistant_service.py`

**Step 1: Write failing tests**

Add tests that:

- Inject a deterministic runtime into `AssistantService`.
- Send a general prompt.
- Assert response comes from runtime.
- Assert audit steps include runtime trace.
- Assert capture and memory proposal paths still produce existing `agent_contract` payloads.

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_assistant_service.py -v
```

Expected:
- FAIL because `AssistantService` does not accept runtime yet.

**Step 2: Implement narrow integration**

- Add optional `agent_runtime` parameter.
- For `general` route only, call `agent_runtime.run(...)` when provided.
- Convert returned trace events to `AssistantAuditStep`.
- Fall back to existing deterministic response on runtime failure.

**Step 3: Verify green**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_assistant_service.py -v
```

Expected:
- PASS.

**Step 4: Commit**

```bash
git add flow/core/services/assistant.py flow/core/engine.py tests/unit/test_assistant_service.py
git commit -m "feat: pilot assistant fallback through agent runtime"
```

### Task 6: Update README and migration notes

**Files:**
- Modify: `README.md`
- Modify: `tasks/todo.md`

**Step 1: Write docs**

Document:

- legacy LLM completion remains supported
- new agent runtime config
- OpenAI Agents SDK first-class target
- Claude Agent SDK and Codex CLI are staged adapter boundaries
- phased migration plan for assistant specialists

**Step 2: Record local results**

Update `tasks/todo.md` with implementation state and verification commands.

**Step 3: Verify docs diff**

Run:
```bash
git diff -- README.md tasks/todo.md
```

Expected:
- README changes are current product docs, not stale CLI/TUI positioning.

**Step 4: Commit**

```bash
git add README.md tasks/todo.md
git commit -m "docs: describe agent runtime migration"
```

### Task 7: Review and full verification

**Files:**
- No direct edits unless review finds issues.

**Step 1: Run code review**

Use `code-review-flow` for changes in `flow/` and `tests/`.

Review checklist:
- no secrets
- no unsafe logs of user prompts
- `flow/models/` stays dependency-light
- no dependency direction violations
- all new public APIs typed
- tests cover runtime failure and optional imports

**Step 2: Run verification**

Run:
```bash
git diff --check
source .venv/bin/activate && pytest tests/unit/test_agent_runtime_contracts.py tests/unit/test_agent_runtime.py tests/unit/test_agent_adapter_imports.py tests/unit/test_assistant_service.py tests/unit/utils/llm/test_config.py -v
source .venv/bin/activate && pytest tests/unit -v
source .venv/bin/activate && ./scripts/test_native_app.sh
source .venv/bin/activate && ./scripts/build_native_app.sh
```

Expected:
- All commands pass.

**Step 3: Fix review or verification issues**

If any command fails, apply `superpowers:systematic-debugging`, write or adjust tests first, then fix.

**Step 4: Final commit if fixes were needed**

Commit any review or verification fixes with a scoped message.

---

## Phase 2 Continuation Tasks

### Task 8: Extend weekly review from read-only guidance into one proposal-producing path

**Files:**
- Modify: `flow/core/services/assistant.py`
- Modify: `tests/unit/test_assistant_service.py`
- Modify: `tests/unit/test_agent_specialists.py`
- Modify: `tests/unit/test_agent_runtime.py`
- Optional: `flow/models/assistant.py` only if one new action type is absolutely required

**Step 1: Keep the scope narrow**

Start with exactly one review action that already fits the current contract vocabulary:
- preferred: `start_weekly_review`
- acceptable: a narrow `clean_up_inbox`

Do not map the full native cleanup vocabulary yet.

**Step 2: Add failing tests**

Add tests for:
- runtime-backed `review` route returning one pending proposal
- proposal conversion through `AgentWriteProposal.to_assistant_proposal()`
- runtime capability rejection when `propose_review_cleanup` is missing

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_assistant_service.py tests/unit/test_agent_specialists.py tests/unit/test_agent_runtime.py -v
```

**Step 3: Implement one bounded proposal path**

- keep existing read-only rendering
- when exactly one allowed write proposal is returned, persist it as the assistant proposal
- do not add multi-proposal selection yet
- do not change native cleanup execution in this task

**Step 4: Verify**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_assistant_service.py tests/unit/test_agent_specialists.py tests/unit/test_agent_runtime.py -v
source .venv/bin/activate && pytest tests/unit -v
source .venv/bin/activate && ./scripts/test_native_app.sh
```

### Task 9: Extend project health from read-only diagnosis into bounded planning proposals

**Files:**
- Modify: `flow/core/services/assistant.py`
- Modify: `tests/unit/test_assistant_service.py`
- Modify: `tests/unit/test_agent_specialists.py`
- Optional: shared proposal execution paths if one existing action type is reused

**Step 1: Reuse the read-only route**

Keep the current `project_health` route detection and context assembly. Add at most one bounded proposal first, using an already-supported planning action when possible.

**Step 2: Add failing tests**

Cover:
- runtime-backed project-health response with one pending proposal
- invalid/disallowed action type rejection
- deterministic fallback still working

**Step 3: Implement**

- persist a proposal only when it fits the current single-proposal assistant turn shape
- keep multi-proposal / complex project reshaping out of scope

**Step 4: Verify**

Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_assistant_service.py tests/unit/test_agent_specialists.py -v
source .venv/bin/activate && pytest tests/unit -v
source .venv/bin/activate && ./scripts/test_native_app.sh
```
