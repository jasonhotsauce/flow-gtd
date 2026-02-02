---
name: textual-ui
description: Expert guidelines for building Textual TUI interfaces with Vim-native navigation and CSS styling. Use when creating screens, widgets, or styling for flow/tui/ components, working with .tcss files, or when the user asks about TUI design patterns.
---

# Textual UI Specialist

Guidelines for building high-performance Textual TUI interfaces in Flow.

## Design Philosophy

- **Speed**: Target 60fps rendering. Avoid heavy calculations in `render()`.
- **Vim-Native**: All lists must support `j/k` navigation. `Esc` to go back.
- **Styling**: Use `.tcss` files exclusively. Never style in Python code.
- **TUI Colocation Rule**:
    - Every new Screen MUST have its own folder inside `flow/tui/screens/`.
    - The Python logic (`.py`) and CSS styles (`.tcss`) MUST be siblings in that folder.
    - **NEVER** put screen-specific CSS in the global `theme.tcss`.

## Widget Pattern

When creating a screen or widget:

1. Define the Python `class` inheriting from `Screen` or `Static`
2. Define the `BINDINGS` list for keyboard shortcuts
3. Provide the accompanying `.tcss` file

### Screen Template

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

class MyScreen(Screen):
    """Screen docstring."""
    
    CSS_PATH = "my_screen.tcss"
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Static("Content")
```

### Widget Template

```python
from textual.widget import Widget
from textual.reactive import reactive

class MyWidget(Widget):
    """Widget docstring."""
    
    value = reactive("")
    
    def render(self) -> str:
        # Keep render() lightweight
        return self.value
```

## Common Components

| Use Case | Widget | Notes |
|----------|--------|-------|
| Task lists | `ListView` | Add `j/k` bindings |
| AI responses | `Markdown` | Streams well |
| Loading states | `LoadingIndicator` | For LLM/DB ops |
| Status messages | `Toast` | Non-blocking alerts |

## Keybinding Standards

```python
BINDINGS = [
    # Navigation
    ("j", "cursor_down", "Down"),
    ("k", "cursor_up", "Up"),
    ("g", "scroll_home", "Top"),
    ("G", "scroll_end", "Bottom"),
    
    # Actions
    ("enter", "select", "Select"),
    ("escape", "app.pop_screen", "Back"),
    ("q", "quit", "Quit"),
    
    # Vim-style
    ("d", "delete", "Delete"),
    ("e", "edit", "Edit"),
]
```

## TCSS Guidelines

Place `.tcss` files alongside their Python modules:

```
flow/tui/
├── screens/
│   ├── inbox.py
│   └── inbox.tcss
└── widgets/
    ├── task_list.py
    └── task_list.tcss
```

### TCSS Template

```css
/* inbox.tcss */
InboxScreen {
    layout: vertical;
}

InboxScreen > ListView {
    height: 1fr;
    border: solid $primary;
}

InboxScreen > ListView:focus {
    border: solid $accent;
}
```

## Performance Rules

1. **Never block in `compose()`** - Use `call_later()` for async setup
2. **Minimize `render()` work** - Cache computed values in reactives
3. **Use `run_worker()`** for LLM/DB calls:

```python
@on(Button.Pressed, "#fetch")
async def handle_fetch(self) -> None:
    self.run_worker(self.fetch_data(), exclusive=True)

async def fetch_data(self) -> None:
    self.query_one(LoadingIndicator).display = True
    result = await db_query()
    self.query_one(LoadingIndicator).display = False
    self.data = result
```

## Anti-Patterns

| Avoid | Instead |
|-------|---------|
| Inline styles in Python | Use `.tcss` files |
| Blocking calls in `compose()` | Use `on_mount()` + workers |
| Complex logic in `render()` | Pre-compute in reactives |
| Arrow key bindings only | Add `j/k/h/l` Vim keys |
