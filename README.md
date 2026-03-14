# Flow GTD

Local-First, AI-Augmented GTD CLI for Senior Engineering Managers (Apple ecosystem).

## Installation

### Homebrew (Recommended)

```bash
brew tap <your-github-username>/flow
brew install flow-gtd
```

### From Source

For development or contributing:

```bash
git clone https://github.com/<your-github-username>/flow-gtd.git
cd flow-gtd
python3.11 -m venv .venv
source .venv/bin/activate
pip3 install poetry
poetry install
```

Optional extras:

```bash
# URL extraction support for `flow save <url>`
poetry install --extras "web"

# Local RAG sidecar stack (ChromaDB + embeddings + PDF parsing)
poetry install --extras "rag"
```

## Resource Storage Options

During setup, Flow asks where to store saved resources:

- `Flow Library`: built-in local storage managed by Flow
- `Obsidian Vault`: resources saved as notes via Obsidian CLI

If you choose Obsidian Vault, install Obsidian CLI and provide your vault path.

## Environment

| Variable | Description |
|----------|-------------|
| `FLOW_DB_PATH` | SQLite path (default: `data/flow.db`) |
| `FLOW_LLM_PROVIDER` | LLM provider override (`gemini`, `openai`, `ollama`) |
| `FLOW_GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini API key |
| `FLOW_OPENAI_API_KEY` | OpenAI API key (when provider is `openai`) |
| `FLOW_OLLAMA_BASE_URL` | Ollama base URL (default: `http://localhost:11434`) |
| `FLOW_RESOURCE_STORAGE` | Resource storage provider (`flow-library`, `obsidian-vault`) |
| `FLOW_OBSIDIAN_VAULT_PATH` | Obsidian vault path when using `obsidian-vault` |
| `FLOW_OBSIDIAN_NOTES_DIR` | Notes subfolder for Flow resources (default: `flow/resources`) |

## Commands

| Command | Description |
|---------|-------------|
| `flow c <text>` | Quick capture alias (supports `--private/-p`) |
| `flow capture <text>` | Full capture command (supports `--private/-p` and `--tags/-t`) |
| `flow save <url\|file\|text>` | Save a resource with automatic LLM tagging to your selected storage backend |
| `flow resources` | List saved resources (optional `--tag`, `--limit`) |
| `flow tags` | List resource tags |
| `flow` | Launch the daily workspace TUI (plan today, execute from editable confirmed state, explicit wrap) |
| `flow tui` | Launch the daily workspace TUI |
| `flow process` | Launch Process Funnel (Dedup → Cluster → 2-Min → Coach) |
| `flow next` | Launch Action screen (next actions + Sidecar: resources matched by task tags) |
| `flow projects` | Launch Projects screen (GTD project list and proceed) |
| `flow sync` | Sync Apple Reminders into Flow (macOS only) |
| `flow sync-status` | Check Reminders permission status |
| `flow review` | Launch Weekly Review (Stale, Someday, Report; contextual actions per section) |
| `flow focus` | Launch Focus Mode (calendar-aware task selection) |
| `flow report` | Print weekly report to stdout |
| `flow version` | Show version |

## Workflow

1. **Capture fast**: `flow c "task"` or Siri → Apple Reminders → `flow sync`
2. **Open the day**: `flow` — if today's plan is missing, build it; otherwise open today's focus list
3. **Process backlog**: `flow process` — deduplicate, cluster into projects, 2-min drill, coach vague tasks
4. **Review projects**: `flow projects` — list active projects, see suggested next action and full task list per project; open a project to complete or defer actions
5. **Execute outside the workspace when needed**: `flow next` or `flow focus` remain available as direct power-user entry points

## Daily Workspace

- `flow` and `flow tui` now open the daily workspace instead of dropping directly into Inbox.
- The daily workspace has three main jobs:
  - `Plan`: build today's Top 3 and Bonus items from visible draft panes fed by candidate buckets (`Must`, `Inbox`, `Ready`, `Suggested`), then press `x` to confirm the plan
  - `Confirmed execution`: keep editing today's Top 3 and Bonus after confirmation while the right side shows grouped unplanned work (`Inbox`, `Next Actions`, `Project Tasks`)
  - `Daily Wrap`: open wrap explicitly with `w` when you want completion counts, accomplishments, carry-forward items, deterministic coaching feedback, and optional AI insight
- Planning stays on one screen: you can add, remove, promote, demote, and reorder draft items without leaving the workspace.
- After you confirm a plan, the same workspace stays live:
  - `[1]` focuses today's ordered plan
  - `[3]` focuses grouped unplanned work on the right
  - `t` / `b` pull selected unplanned work into Top 3 or Bonus
  - `d` removes a planned item back to its original unplanned group
  - `c` completes the selected planned item
- If Top 3 is already full, adding unplanned work into Top 3 opens a chooser so you can demote one current Top 3 item into Bonus.
- The detail pane now shows task metadata plus concise tag-matched and semantic resources for the selected planned or unplanned item.
- If Flow detects a prior day with an unwrapped plan, startup routes you through that prior daily wrap before opening today's normal planning/execution flow.
- Inbox, Projects, Review, and Someday remain part of the TUI model; the workspace is the default entry point, not a replacement for GTD structure.

## TUI Panel Shortcuts

- On split-panel screens (`Inbox`, `Projects`, `Next Actions`), switch focus with:
  - `1` / `2` for first/second panel
  - Panel abbreviations shown in panel headers (for example `l`, `d`, `t`, `r`, `e`)
- `Tab` focus switching remains available on the Next Actions screen.

## Focus + Inbox Empty States

- Focus and Inbox use a centered minimalist empty state with an ASCII visual anchor, concise status header, and a high-contrast action hint.
- Focus empty state keeps `n` as the fastest path to Inbox quick capture.
- Inbox empty state also supports `n` to open quick capture immediately.
- A randomized one-line productivity tip appears at the bottom of both empty states.

## Tech

- **CLI**: Typer  
- **TUI**: Textual  
- **DB**: SQLite (local)  
- **LLM**: Multi-provider adapter (Gemini default, OpenAI/Ollama optional)  
- **Sync**: PyObjC EventKit (macOS)

## Tests

```bash
pytest tests/unit -v
```

## Development

### Make Targets

```bash
make help          # Show all available targets
make test          # Run tests
make build         # Build wheel and sdist
make bump-patch    # Bump version (0.1.0 → 0.1.1)
make release       # Create GitHub release
make brew-formula  # Generate Homebrew formula
make publish       # Full release workflow
```

## License

MIT License - see [LICENSE](LICENSE) for details.
