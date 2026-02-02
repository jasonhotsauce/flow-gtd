# Flow GTD

Local-First, AI-Augmented GTD CLI for Senior Engineering Managers (Apple ecosystem).

## Install

```bash
poetry install
# or: pip install -e .
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

## Environment

| Variable | Description |
|----------|-------------|
| `FLOW_DB_PATH` | SQLite path (default: `data/flow.db`) |
| `FLOW_CHROMA_PATH` | ChromaDB path (default: `data/knowledge_base`) |
| `FLOW_GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini API key (optional; AI features need it) |

## Commands

| Command | Description |
|---------|-------------|
| `flow c <text>` / `flow capture <text>` | Quick capture to inbox |
| `flow tui` | Launch TUI (Inbox) |
| `flow process` | Launch Process Funnel (Dedup → Cluster → 2-Min → Coach) |
| `flow next` | Launch Action screen (next actions + RAG Sidecar) |
| `flow sync` | Sync Apple Reminders into Flow (macOS only) |
| `flow review` | Launch Weekly Review (Stale, Someday, Report) |
| `flow report` | Print weekly report to stdout |
| `flow version` | Show version |

## Workflow

1. **Capture**: `flow c "task"` or Siri → Apple Reminders → `flow sync`
2. **Process**: `flow process` — deduplicate, cluster, 2-min drill, coach vague tasks
3. **Execute**: `flow next` — next actions list + RAG Sidecar (related docs)

## Tech

- **CLI**: Typer  
- **TUI**: Textual  
- **DB**: SQLite, ChromaDB (local)  
- **LLM**: Google GenAI (Gemini 2.0 Flash)  
- **Sync**: PyObjC EventKit (macOS)

## Tests

```bash
pytest tests/unit -v
```

## License

See project license.
