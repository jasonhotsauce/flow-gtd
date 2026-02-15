# Flow: Strategic Vision & Architectural Audit Guide

**Version:** 0.1.6 Audit Context
**Target Audience:** AI Code Assistant (Codex) / Lead Architect
**Purpose:** To audit the current v0.1.6 codebase against the core product philosophy, competitive moats, and retention mechanics. Do not refactor code that violates these principles; rewrite it to align with them.

---

## 1. Core Objectives (The "Why")

**Flow** is a Local-First, AI-Native GTD (Getting Things Done) CLI tool engineered exclusively for Senior Engineering Managers and Architects. 

The primary objective is **Cognitive Offloading**. The tool must minimize Context Switching Costs and Process Friction by transforming discipline into an algorithmic pipeline.

**The Golden Pipeline:**
1. **Ingest (Zero-Friction):** Dumb capture via CLI or Apple Reminders. No metadata required at input.
2. **Refine (AI Funnel):** LLM-driven batch processing (Deduplication, Clustering, Socratic Coaching).
3. **Execute (Contextual Focus):** Just-in-Time (JIT) RAG sidecar to retrieve context, or Heuristic Dispatching for deep focus.

---

## 2. Competitive Advantage (The Moat)

The codebase must maintain strict differentiation from existing COTS (Commercial Off-The-Shelf) productivity software. When reviewing features, ensure they align with the Flow Advantage.

| Competitor Archetype | Examples | The Fatal Flaw | The Flow Advantage (Codebase Requirement) |
| :--- | :--- | :--- | :--- |
| **Lightweight Lists** | Apple Reminders, Todoist | Unstructured dumping ground leading to task rot and decision paralysis. | **The AI Funnel:** The code must enforce batch processing via K-Means or LLM clustering to group raw inputs into actionable `Projects`. |
| **Heavyweight GTD** | OmniFocus, Things 3 | Maintenance Overhead > Execution ROI. Requires manual tagging and sorting. | **AI-Compensated Discipline:** The system must never ask the user to manually enter tags or dates during capture. Metadata must be extracted by the LLM in the background. |
| **All-in-One Wikis** | Notion, Obsidian | GUI latency, fragile systems, encourages "meta-work" (tweaking the tool instead of working). | **Opinionated CLI/TUI:** High-performance, keyboard-driven interface. Async execution (`asyncio` / `Textual` workers) is mandatory for 60fps responsiveness. |
| **AI Auto-Schedulers** | Motion, Reclaim.ai | Rigid calendar blocking causes anxiety and removes user agency. | **Context-Aware Dispatching:** Do not block time. Use `EventKit` heuristically to calculate available time windows and suggest the single best task (`flow focus`). |

---

## 3. User Retention & Stickiness Design

Productivity tools die from user guilt (accumulated overdue tasks). The codebase must hardcode psychological safety nets.

### A. The Guilt-Relief Valve (Bankruptcy Protocol)
- **Mechanism:** The system must proactively detect stale tasks (`created_at > 14 days` or `status = 'inbox' > 7 days`).
- **Audit Check:** Ensure there is a mechanism (e.g., in the Review module) that allows bulk archiving to a `someday` or `backlog` state without flashing red warnings. The tool must be forgiving.

### B. The Micro-Habit Loop
- **Mechanism:** Triage (`flow process`) must take less than 3 minutes.
- **Audit Check:** Verify the implementation of the **2-Minute Drill**. The TUI must allow single-keystroke execution (Do/Defer/Delete) for tasks with low estimated effort before engaging the heavy LLM coach.

### C. Write-Only Memory Prevention (JIT RAG)
- **Mechanism:** Users forget what reference materials they save.
- **Audit Check:** Verify the ChromaDB implementation. The RAG Sidecar must automatically trigger an async semantic search based on the currently highlighted task in the TUI, pushing relevant URLs/PDFs to the user without manual searching.

### D. The Socratic Coach (Progressive Fading)
- **Mechanism:** The AI should not do the work for the user; it should coach them to write better tasks.
- **Audit Check:** Review the LLM Prompts. If the user inputs "fix bug", the LLM should *not* just append random context. It must challenge the user to use an actionable verb (e.g., "Analyze memory leak logs").

---

## 4. Engineering Audit Directives for Codex

When reviewing the v0.1.6 codebase, enforce the following constraints:

1. **Local-First Sanctity:** Ensure SQLite and ChromaDB data never leak to external APIs. Only task titles/descriptions should be sent to the LLM Provider.
2. **Adapter Pattern Verification:** Check the LLM integration. It must use an interface (`LLMProvider`) allowing seamless swapping between Gemini, OpenAI, and local Ollama based on `~/.flow/config.toml`.
3. **Async UI Performance:** Inspect all `Textual` event handlers (`@on`). Any operation involving Disk I/O, SQLite transactions, or HTTP calls MUST be offloaded to `self.run_worker()` to prevent UI freezing.
4. **Apple Bridge Safety:** Review `pyobjc` EventKit code. Ensure non-destructive syncing (e.g., marking Apple Reminders as completed or moving them to a specific list, rather than hard deleting them).
