"""Tests for Flow library resource store provider."""

from __future__ import annotations

import tempfile
from pathlib import Path

from flow.core.resources.models import ResourceRecord
from flow.core.resources.providers.flow_library import FlowLibraryResourceStore
from flow.database.resources import ResourceDB


def _new_store(tmp_path: Path) -> FlowLibraryResourceStore:
    db = ResourceDB(tmp_path)
    db.init_db()
    return FlowLibraryResourceStore(db)


def test_flow_library_store_search_by_tags_matches_resource_db_behavior() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = Path(handle.name)

    store = _new_store(db_path)

    first = ResourceRecord(
        id="r1",
        content_type="url",
        source="https://one.example.com",
        tags=["api", "backend"],
    )
    second = ResourceRecord(
        id="r2",
        content_type="url",
        source="https://two.example.com",
        tags=["api"],
    )

    store.save_resource(first)
    store.save_resource(second)

    results = store.search_by_tags(["api", "backend"])

    assert [item.id for item in results] == ["r1", "r2"]


def test_flow_library_store_round_trip_and_tags() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = Path(handle.name)

    store = _new_store(db_path)

    record = ResourceRecord(
        id="resource-123",
        content_type="text",
        source="hello",
        tags=["notes", "daily"],
    )

    store.save_resource(record)
    fetched = store.get_resource("resource-123")

    assert fetched is not None
    assert fetched.id == "resource-123"
    assert sorted(store.list_tags()) == ["daily", "notes"]


def test_flow_library_store_health_check_ok() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = Path(handle.name)

    store = _new_store(db_path)

    result = store.health_check()

    assert result.ok is True
