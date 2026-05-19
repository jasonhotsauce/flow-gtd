# Agent Runtime SDK Design

## Goal

Refactor Flow's LLM layer toward an agent runtime that can support orchestrated assistant workflows and future compatibility with OpenAI Agents SDK, Claude Agent SDK, and Codex-style coding agents.

## Decision

Build a Flow-owned agent runtime abstraction first, then implement providers behind it incrementally.

The product assistant should depend on Flow's contracts, not directly on OpenAI, Claude, or Codex APIs. Existing `flow.utils.llm.complete*` callers stay compatible while high-value assistant flows migrate route by route to the new runtime.

## Context

Current state:

- `flow/utils/llm/` exposes text, JSON, stream, and async completion facades over Gemini, OpenAI, and Ollama providers.
- Existing coach, tag extraction, and recap paths call `complete` or `complete_json` directly.
- `flow/core/services/assistant.py` is deterministic routing with persisted turns, audit steps, proposal confirmation, and explicit `agent_contract` validation.
- The native app already treats assistant proposals as bounded, confirmation-gated operations.

Target state:

- Product assistant orchestration runs through Flow agent contracts.
- OpenAI Agents SDK is the first full product-runtime adapter.
- Claude Agent SDK and Codex CLI compatibility are represented as adapter boundaries without forcing coding-agent semantics into normal assistant chat.
- Existing completion APIs remain stable until each caller is deliberately migrated.

## Architecture

### Flow Agent Contracts

Create `flow/agents/` with dependency-light models:

- `AgentRequest`: user input, route hint, context snapshot, allowed capabilities, output mode, and metadata.
- `AgentResult`: final response text, optional structured output, write proposals, trace events, usage metadata, provider name, and model name.
- `AgentTraceEvent`: normalized orchestration/audit event with stage, summary, payload, provider, and timestamp.
- `AgentCapability`: enum-like strings for read-only GTD context, propose inbox writes, propose memory writes, propose planning changes, propose review cleanup, tool execution, and coding workspace access.
- `AgentWriteProposal`: runtime-native proposal representation that can be converted into existing `AssistantProposal` payloads with `agent_contract`.

### Runtime Boundary

Create `flow/agents/runtime.py`:

- Owns adapter selection from config.
- Normalizes exceptions into safe `AgentResult` failures.
- Appends runtime trace events.
- Validates output and write proposals before returning to assistant services.
- Provides sync and async entry points, with sync implemented over the adapter's sync method or an event-loop-safe async bridge.

### Adapter Boundary

Create `flow/agents/adapters/`:

- `base.py`: `AgentRuntimeAdapter` protocol.
- `deterministic.py`: test/local adapter used for deterministic migration and unit tests.
- `openai_agents.py`: first full SDK adapter, optional dependency, import-lazy.
- `claude_agent.py`: adapter shell for Claude Agent SDK; disabled unless configured and installed.
- `codex_cli.py`: adapter shell for headless Codex CLI; scoped to coding/dev workflows, not normal product chat.

### Assistant Integration

The first assistant integration should be narrow:

- Keep deterministic route detection in `AssistantService` initially.
- Route only general assistant response generation, or one low-risk proposal path, through `AgentRuntime`.
- Convert runtime trace events into existing `AssistantAuditStep`.
- Convert runtime write proposals into existing `AssistantProposal` and embedded `AssistantAgentContract`.
- Preserve confirmation and DB persistence validation as the final write boundary.

## Gradual Migration Plan

### Phase 0: Compatibility Foundation

- Add `flow/agents/` contracts, runtime, deterministic adapter, and tests.
- Add config fields for `agent_runtime` without removing `llm.provider`.
- Keep `flow.utils.llm.complete*` unchanged.
- README documents that legacy LLM completion and new agent runtime coexist during migration.

### Phase 1: Assistant Runtime Pilot

- Inject optional `AgentRuntime` into `AssistantService`.
- Migrate fallback/general assistant response to runtime first because it has no write side effects.
- Keep capture and memory proposal construction deterministic until runtime proposal validation has dedicated tests.
- Persist runtime trace events as audit steps.

### Phase 2: Proposal-Producing Specialists

- Add specialist definitions for:
  - Inbox Clarifier
  - Daily Planner
  - Weekly Reviewer
  - Project Health Analyst
  - Memory Curator
- Migrate proposal-producing flows one at a time.
- For each migrated flow, require:
  - structured output schema
  - `agent_contract` conversion test
  - confirmation-required write test
  - existing native smoke coverage still passing

### Phase 3: OpenAI Agents SDK Adapter

- Add optional `openai-agents` dependency extra.
- Implement adapter using SDK agents, tools, guardrails, handoffs, sessions, and trace mapping.
- Keep SDK imports lazy so tests and local installs do not require an API key or package installation.
- Use mocks/fakes for unit tests; no live API calls in default test suite.

### Phase 4: Claude Agent SDK and Codex Adapter Boundaries

- Implement Claude Agent SDK adapter for configured environments where built-in tools, sessions, permissions, MCP, or subagents are required.
- Implement Codex CLI adapter only for dev/coding-agent workflows, with explicit workspace and command permissions.
- Do not expose Codex as a normal product chat backend unless a future product decision says Flow should delegate user GTD content to a coding agent.

### Phase 5: Legacy Completion Retirement

- Migrate coach, tag extraction, recap insights, and any remaining `complete*` users to runtime only after their behavior is covered by tests.
- Keep a compatibility wrapper until no supported caller depends on provider-specific completion semantics.
- Remove legacy providers only when README, config migration, and full verification prove no active path needs them.

## Safety Rules

- No autonomous database, Reminders, Calendar, or file writes from an agent result.
- All write-capable output must produce an `AgentWriteProposal` and existing `agent_contract`.
- Low-confidence, warned, or blocked proposals must require confirmation.
- Provider errors should degrade to deterministic assistant responses where practical.
- Sensitive task content must not be logged in provider exception messages or trace summaries.

## Testing Strategy

- Unit tests for contract validation and serialization.
- Runtime tests with deterministic adapter.
- Assistant integration tests for fallback route and audit trace persistence.
- Config tests for new runtime provider fields.
- Import tests proving OpenAI/Claude/Codex adapters are lazy and optional.
- Existing verification remains required:
  - `source .venv/bin/activate && pytest tests/unit -v`
  - `source .venv/bin/activate && ./scripts/test_native_app.sh`
  - `source .venv/bin/activate && ./scripts/build_native_app.sh`

## Success Criteria

- The new runtime exists behind Flow-owned contracts.
- Existing completion API remains compatible.
- Assistant can use runtime for at least one side-effect-free route.
- Migration plan for proposal-producing specialist agents is explicit.
- No test requires live OpenAI, Anthropic, or Codex credentials.
