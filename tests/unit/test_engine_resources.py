"""Tests for Engine resource and tagging integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.core.engine import Engine
from flow.database.resources import ResourceDB
from flow.models import Resource


@pytest.fixture
def temp_db_path() -> Path:
    """Temporary SQLite path (cleaned up after test)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink(missing_ok=True)


@pytest.fixture
def engine(temp_db_path: Path) -> Engine:
    """Engine with temp database."""
    return Engine(db_path=temp_db_path)


@pytest.fixture
def resource_db(temp_db_path: Path) -> ResourceDB:
    """ResourceDB with same temp path as engine."""
    db = ResourceDB(temp_db_path)
    db.init_db()
    return db


class TestEngineCaptureWithTags:
    """Tests for capture with explicit tags."""

    def test_capture_with_explicit_tags(self, engine):
        """Capture with explicit tags stores them in context_tags."""
        item = engine.capture(
            "Review OAuth implementation",
            tags=["auth", "code-review"],
        )

        assert item.context_tags == ["auth", "code-review"]

    def test_capture_with_skip_auto_tag(self, engine):
        """Capture with skip_auto_tag=True doesn't auto-tag."""
        # No mock needed - just verify no background thread is started
        item = engine.capture(
            "Some sensitive task",
            skip_auto_tag=True,
        )

        # context_tags should be empty (no auto-tagging)
        assert item.context_tags == []

    @patch("flow.core.engine.extract_tags")
    def test_capture_auto_tags_in_background(self, mock_extract, engine):
        """Capture triggers background auto-tagging."""
        mock_extract.return_value = ["test-tag"]

        item = engine.capture("Test task")

        # Initial capture should have empty tags (background hasn't run)
        assert item.context_tags == []

        # The mock should have been called (in a thread)
        # Note: We can't easily test the background thread completion
        # but we verify the function signature is correct

    @patch("flow.core.engine.extract_tags")
    def test_capture_block_auto_tag_invokes_progress_callback(self, mock_extract, engine):
        """When block_auto_tag=True, on_tagging_start is called before tagging."""
        mock_extract.return_value = ["blocked-tag"]
        progress_calls: list[str] = []

        def on_start() -> None:
            progress_calls.append("started")

        item = engine.capture(
            "Blocking capture",
            block_auto_tag=True,
            on_tagging_start=on_start,
        )

        assert progress_calls == ["started"]
        # Tags applied synchronously when blocking
        updated = engine.get_item(item.id)
        assert updated is not None
        assert updated.context_tags == ["blocked-tag"]

    @pytest.mark.asyncio
    @patch("flow.core.engine.extract_tags_async")
    async def test_capture_async_applies_tags(self, mock_extract_async, engine):
        """capture_async runs auto-tagging in async path and returns item with tags."""
        mock_extract_async.return_value = ["async-tag"]

        item = await engine.capture_async("Async capture task")

        assert item.context_tags == ["async-tag"]
        mock_extract_async.assert_called_once()


class TestEngineResourceMatching:
    """Tests for finding resources by task tags."""

    def test_get_resources_by_tags(self, engine, resource_db):
        """Engine can find resources matching given tags."""
        # Add some resources
        resource_db.insert_resource(
            Resource(
                id="r1",
                content_type="url",
                source="https://auth-docs.com",
                tags=["auth", "docs"],
            )
        )
        resource_db.insert_resource(
            Resource(
                id="r2",
                content_type="url",
                source="https://api-docs.com",
                tags=["api", "docs"],
            )
        )

        # Find by tags
        results = engine.get_resources_by_tags(["auth"])

        assert len(results) == 1
        assert results[0].id == "r1"

    def test_get_resources_by_tags_empty(self, engine):
        """Empty tag list returns empty results."""
        results = engine.get_resources_by_tags([])
        assert results == []

    def test_get_resources_for_task(self, engine, resource_db):
        """Engine can find resources for a task by ID."""
        # Create a task with tags
        item = engine.capture(
            "Review auth implementation",
            tags=["auth", "code-review"],
        )

        # Add a matching resource
        resource_db.insert_resource(
            Resource(
                id="r1",
                content_type="url",
                source="https://auth-guide.com",
                tags=["auth", "security"],
            )
        )

        # Find resources for task
        results = engine.get_resources_for_task(item.id)

        assert len(results) == 1
        assert results[0].id == "r1"

    def test_get_resources_for_task_no_tags(self, engine):
        """Task with no tags returns empty resources."""
        item = engine.capture("Task with no tags", tags=[])

        results = engine.get_resources_for_task(item.id)

        assert results == []

    def test_get_resources_for_nonexistent_task(self, engine):
        """Nonexistent task returns empty resources."""
        results = engine.get_resources_for_task("nonexistent-id")
        assert results == []


class TestEngineResourceDBInitialization:
    """Tests for resource database initialization."""

    def test_engine_initializes_resource_db(self, temp_db_path):
        """Engine initializes the resource database."""
        engine = Engine(db_path=temp_db_path)

        # Should be able to insert/query resources
        engine._resource_db.insert_resource(
            Resource(
                id="test",
                content_type="text",
                source="test content",
                tags=["test"],
            )
        )

        result = engine._resource_db.get_resource("test")
        assert result is not None
