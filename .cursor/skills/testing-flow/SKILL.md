---
name: testing-flow
description: Standards for testing Flow CLI and TUI components. Use when writing tests, creating test fixtures, mocking external services, or working with files in tests/**/*.py or **/*_test.py.
---

# Testing Flow: QA Standards

## Framework

Use `pytest` with `pytest-asyncio` for all async code.

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_call()
    assert result is not None
```

## Database Fixture

Use in-memory SQLite. **NEVER** touch the real `flow.db`.

```python
import sqlite3
import pytest

@pytest.fixture
def db():
    """In-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    # Run schema setup here
    yield conn
    conn.close()
```

## External API Mocking

### Google GenAI

Mock all LLM calls to save cost and ensure deterministic tests.

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_genai():
    with patch("google.genai.GenerativeModel") as mock:
        mock.return_value.generate_content_async = AsyncMock(
            return_value=MockResponse(text="mocked response")
        )
        yield mock
```

### Apple EventKit

Mock PyObjC bindings. **NEVER** modify user's real reminders.

```python
@pytest.fixture
def mock_eventkit():
    with patch("flow.sync.reminders.EKEventStore") as mock_store:
        mock_store.return_value.requestAccessToEntityType_completion_ = (
            lambda t, cb: cb(True, None)
        )
        yield mock_store
```

### ChromaDB

Use ephemeral client for lightweight vector store testing.

```python
import chromadb

@pytest.fixture
def mock_chroma():
    """In-memory ChromaDB for testing."""
    client = chromadb.Client()  # Ephemeral by default
    yield client
```

## TUI Testing

Use Textual's test harness with pilot for simulating user input.

```python
from flow.tui.app import FlowApp

@pytest.mark.asyncio
async def test_tui_navigation():
    app = FlowApp()
    async with app.run_test() as pilot:
        # Simulate keystrokes
        await pilot.press("j")  # Move down
        await pilot.press("k")  # Move up
        await pilot.press("enter")  # Select
        
        # Assert on app state
        assert app.query_one("#task-list").highlighted is not None
```

## Test Organization

```
tests/
├── conftest.py          # Shared fixtures (db, mocks)
├── test_cli/            # CLI command tests
├── test_tui/            # TUI screen/widget tests
├── test_sync/           # Apple Reminders sync tests
└── test_intelligence/   # LLM/RAG tests
```
