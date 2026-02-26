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

## Environment

| Variable | Description |
|----------|-------------|
| `FLOW_DB_PATH` | SQLite path (default: `data/flow.db`) |
| `FLOW_LLM_PROVIDER` | LLM provider override (`gemini`, `openai`, `ollama`) |
| `FLOW_GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini API key |
| `FLOW_OPENAI_API_KEY` | OpenAI API key (when provider is `openai`) |
| `FLOW_OLLAMA_BASE_URL` | Ollama base URL (default: `http://localhost:11434`) |

## Commands

| Command | Description |
|---------|-------------|
| `flow c <text>` | Quick capture alias (supports `--private/-p`) |
| `flow capture <text>` | Full capture command (supports `--private/-p` and `--tags/-t`) |
| `flow save <url\|file\|text>` | Save a resource (URL, file path, or text) with automatic LLM tagging; use `--private` for manual tags |
| `flow resources` | List saved resources (optional `--tag`, `--limit`) |
| `flow tags` | List all tags with usage counts |
| `flow tui` | Launch TUI (Inbox) |
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

1. **Capture**: `flow c "task"` or Siri → Apple Reminders → `flow sync`
2. **Save resources**: `flow save <url>`, `flow save <file>`, or `flow save "text"` — URLs, files, or text with automatic tagging for task matching
3. **Process**: `flow process` — deduplicate, cluster into projects, 2-min drill, coach vague tasks
4. **Projects** (GTD review): `flow projects` — list active projects, see suggested next action and full task list per project; open a project to complete or defer actions
5. **Execute**: `flow next` — next actions list + Sidecar (resources matched by task tags)

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
