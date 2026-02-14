# Product Requirements Document: Flow
**Version**: 1.0.0 (Release Candidate) 
**Status**: Approved for Development 
**Tech Stack**: Python (Typer/Textual), SQLite, ChromaDB, Multi-LLM (Gemini/OpenAI/Ollama), PyObjC

## 1. Executive Summary
**Flow** is a **Local-First, AI-Native GTD CLI** tool explicitly designed for Senior Engineering Managers and Architects.
It addresses two specific pain points inherent to the role: **High Context Switching Costs** and **Input Fragmentation**. Flow achieves "Cognitive Offloading" through three core strategies:

1. **Zero-Friction Capture**: Utilizing the Apple ecosystem as a "dumb terminal" for brain dumps.
2. **The AI Funnel**: Algorithmic processing of the "Clarify/Organize" GTD phases using LLMs for deduplication, clustering, and Socratic coaching.
3. **Contextual Execution**: Just-in-Time (JIT) context retrieval via RAG (Retrieval-Augmented Generation) during the execution phase.

## 2. Core User Loop
The system operates on a unidirectional data pipeline: **Ingest (Input) -> Refine (Throughput) -> Execute (Output)**.

### 2.1 Phase 1: Ingest
* **State**: Chaotic, Unstructured.
* **Action**: User inputs raw thoughts via CLI hotkeys or Siri (Apple Reminders).
* **System Behavior**: Stores data and scrapes metadata. No cleaning or questioning occurs at this stage.

### 2.2 Phase 2: The AI Process Funnel
* **State**: Wizard Mode (Staged Batch Processing).
* **Action**: User runs flow process. The user must pass through 4 filters sequentially:
  1. **Garbage Collection**: Automatically identifies Reference materials (offloads to Vector DB) and Trash.
  2. **Semantic Clustering**: AI identifies topics (e.g., "HLS Bug") and suggests grouping into Projects.
  3. **Rapid Fire**: 2-Minute Rule filter (Do Now / Defer / Delete).
  4. **Socratic Coaching**: Challenges remaining vague tasks (e.g., "Fix Bug") to force conversion into Actionable Verbs.

### 2.3 Phase 3: Execute
* **State**: Highly Focused.
* **Action**: User runs flow next or flow projects.
* **System Behavior**:
  * **flow next**: Displays a filtered list of Next Actions; the Sidecar automatically pushes relevant context (RAG) based on the selected task.
  * **flow projects**: GTD project list — view all active projects with suggested next action and full task list; open a project to complete or defer actions (see [Projects feature](features/projects.md)).

## 3. Functional Requirements
**Module A: Universal Capture & Sync**

| ID | Feature | Description | Technical Constraints |
| ---- | ---- | ---- | ---- |
| A.1 |	**CLI Capture** | flow c <text> 极速写入 SQLite Inbox 表。|	启动延迟 < 100ms。|
| A.2 | Context Hook | Capture metadata from the active App (Xcode File/Line, Browser URL, Git Branch). | Use NSWorkspace + AppleScript. Store as JSON Payload. |
| A.3 | Apple Bridge | Background Daemon for bi-directional sync with Apple Reminders. | **Safety Rule**: Move imported Reminders to a "Flow-Imported" list. **NEVER physically delete**. |
| A.4 | Auto-Index | Automatically download and vectorize content if the capture contains URLs/PDF paths. | Async processing; must not block CLI return. |

**Module B: The Process Funnel (AI Logic)**
Interaction model is a **TUI Wizard** (Textual App), fully keyboard-driven.
  1. Stage 1: Deduplication
     * Logic: LLM compares semantic similarity.
     * UI: Split View (Candidate A vs B). Actions: Merge, Keep Both.
  2. Stage 2: Project Clustering
     * Logic: LLM detects dense topic clusters.
     * UI: Card Stack. Actions: Create Project, Ungroup.
  3. Stage 3: 2-Minute Drill
     * Logic: Filters tasks with estimated effort < 5min.
     * UI: Single Card + Timer Overlay. Actions: Cmd+1(Do), Cmd+2(Defer).
  4. Stage 4: The Coach
     * Logic: Prompt Engineering for vague tasks.
     * UI: Chat Interface. Actions: Select AI suggestion or Edit manually.

**Module C: Action Dashboard & RAG**
**Layout**: Split Screen (66% List / 33% Sidecar).
  * **View Logic (SQL View):**
    * Show only status='active'.
    * Project Logic:
      * `Sequential Project`: Show only the first incomplete child task (Blocker logic).
      * `Parallel Project`: Show all child tasks.
  * **Sidecar (Just-in-Time RAG):**
      * Trigger: on_list_highlight (Debounced 300ms).
      * Query: Embed current task title -> Search ChromaDB -> Return Top 3 Docs/Links.
      * Content: Display filename, similarity score, and snippet. Support Tab key to focus and open links.

**Module D: Weekly Review**
* **Stale Detection**: Scan tasks where created_at < -14 days. Suggest archiving.
* **Someday Resurface**: Scan status='someday'. If semantically relevant to a current Active Project, suggest "resurfacing".
* **Report**: Generate a Markdown/ASCII Weekly Report (Velocity, Completed Items).

**Module E: Deep Focus Mode (`flow focus`)**
* **Concept**: "Context-Aware Tunnel Vision". Automatically selects the *best possible task* based on user's current time constraints and energy, not just static priority.
* **Logic: The Smart Dispatcher**:
    1. **Calendar Check**: System queries `EventKit` to find the start time of the next meeting.
    2. **Time Window Calculation**: `Available_Slots = Next_Event_Start - Current_Time`.
    3. **Selection Algorithm**:
        * *If `Available_Slots` < 30 mins*: Filter for tasks with `duration="short"` or `tag="@admin"`. (Quick Wins).
        * *If `Available_Slots` > 2 hours*: Prioritize tasks with `energy="high"` and `priority=1`. (Deep Work).
        * *Fallback*: If no calendar data, default to standard Priority sort.
* **UI Layout**:
    * **Header**: "Focus Mode (You have 45 mins before 'Weekly Sync')"
    * **Center**: The Task Title (large, centered).
    * **Footer**: [Space] Complete | [S] Skip (Too hard right now) | [Esc] Exit.
* **Technical Requirements**:
    1. **Schema**: Add `estimated_duration` (integer, minutes) to `items` table.
    2. **Process Funnel**: The LLM must estimate duration during the "Coaching" phase if missing (e.g., "Review PR" -> 15m).
    3. **Real-time Hook**: `flow focus` triggers a synchronous `EventKit` read (cached for 5 mins) to determine the time window.

**Module F: Onboarding Wizard (First Run Experience)**
* **Goal**: Guide new users to configure LLM providers and validate credentials via an interactive TUI wizard.
* **Trigger Logic**:
    * On application launch, check `~/.flow/config.toml`.
    * If file missing OR `onboarding_completed != true`, launch `OnboardingApp` instead of `MainApp`.
* **UI Flow (3 Screens)**:
    1. **Screen 1: Provider Selection**
        * Widget: `RadioSet` with options: Gemini, OpenAI, Ollama.
        * Keybindings: `j/k` navigation, `Enter` to confirm.
        * Displays provider-specific hints (e.g., "Gemini: Free tier available").
    2. **Screen 2: Credentials Form**
        * Dynamic form based on selected provider:
            * Gemini/OpenAI: `Input` for API key (password mode) + "Get Key" button (opens browser).
            * Ollama: `Input` for server URL (default: `http://localhost:11434`).
    3. **Screen 3: Validation**
        * Shows `LoadingIndicator` during validation.
        * Tests connection by instantiating provider and sending a ping request.
        * On success: Writes config to `~/.flow/config.toml` with `chmod 600`, then exits to launch main app.
        * On failure: Shows error message with "Retry" and "Back" buttons.
* **Technical Constraints**:
    * Do NOT use `print()` or `input()`. Use Textual widgets exclusively.
    * Config file must have secure permissions (`0o600`).
    * Validation timeout: 10 seconds.

## 4. Technical Architecture
### 4.1 Data Schema (SQLite)
**Uses a Polymorphic Design.**
```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    type TEXT,             -- 'inbox', 'action', 'project', 'reference'
    title TEXT,
    status TEXT,           -- 'active', 'done', 'waiting', 'someday', 'archived'
    context_tags TEXT,     -- JSON: ["@xcode", "@office"]
    parent_id TEXT,        -- FK to items.id (Project linkage)
    created_at DATETIME,
    due_date DATETIME,
    meta_payload JSON,     -- {"app": "Xcode", "file": "Player.swift", "line": 42}
    original_ek_id TEXT,   -- Apple EventKit ID (Sync tracking)
    estimated_duration INTEGER  -- Task duration in minutes (for Focus Mode)
);

-- Indexing needed for performance
CREATE INDEX idx_status_type ON items(status, type);
CREATE INDEX idx_parent ON items(parent_id);
```
### 4.2 Intelligence Layer
* **LLM**: Multi-provider support via Strategy Pattern.
  * **Providers**: Gemini (google-genai), OpenAI (openai SDK), Ollama (httpx).
  * **Default**: Gemini 2.0 Flash.
  * **Config**: `~/.flow/config.toml` or environment variables (`FLOW_LLM_PROVIDER`).
  * **JSON Parsing**: Robust parser handles varied model output formats.
* **Vector DB**: ChromaDB (Persistent Local Mode).
* **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (Local Inference).

#### LLM Configuration Example (`~/.flow/config.toml`)
```toml
[llm]
provider = "gemini"  # "gemini", "openai", "ollama"

[llm.gemini]
api_key = ""  # or FLOW_GEMINI_API_KEY env var
default_model = "gemini-2.0-flash"

[llm.openai]
api_key = ""  # or FLOW_OPENAI_API_KEY env var
default_model = "gpt-4o-mini"
base_url = ""  # optional, for Azure/custom endpoints

[llm.ollama]
base_url = "http://localhost:11434"
default_model = "llama3.2"
```

### 4.3 macOS Integration
* **Library**: pyobjc-framework-EventKit.
* **Permissions**: Code must explicitly handle EKAuthorizationStatus.

## 5. Non-Functional Requirements
1. **Privacy**:
   * Vector DB data must NEVER be uploaded to the cloud.
   * LLM calls send only Task Title/Description, not full attachment content (unless explicitly authorized).
2. Performance:
   * TUI Rendering: > 60fps.
   * RAG Queries: Must run in a Worker Thread to prevent blocking the UI Main Thread.
3. Resilience:
   * Offline Mode: If network fails, AI features (Clustering, Coach) must degrade gracefully (Disable or Prompt Retry), while core CRUD remains functional.

## 6. Implementation Roadmap

* Phase 1: Skeleton (Day 1)
  * Initialize poetry, typer, textual.
  * Implement sqlite_db.py and InboxManager.
* Phase 2: The Bridge (Day 2)
  * Implement RemindersSync (EventKit).
  * Implement ContextHook (AppleScript).
* Phase 3: The Dashboard (Day 3)
  * Build ActionScreen (TUI) with Split View.
  * Implement VectorStore (ChromaDB) and wire up the Sidecar.
* Phase 4: The Brain (Day 4)
  * Implement ProcessScreen (The Funnel logic).
  * Integrate Gemini 3 for the "Coach" agent.