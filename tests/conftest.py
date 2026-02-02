"""Global fixtures: temp DB, mock LLM/EventKit/Chroma."""

import tempfile
from pathlib import Path

import pytest

from flow.database.sqlite import SqliteDB
from flow.models import Item


@pytest.fixture
def temp_db_path() -> Path:
    """Temporary SQLite path (cleaned up after test)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink(missing_ok=True)


@pytest.fixture
def db(temp_db_path: Path) -> SqliteDB:
    """Initialized SqliteDB with temp path."""
    d = SqliteDB(temp_db_path)
    d.init_db()
    return d


@pytest.fixture
def sample_item() -> Item:
    """Single inbox item for tests."""
    return Item(
        id="test-id-1",
        type="inbox",
        title="Test task",
        status="active",
    )
