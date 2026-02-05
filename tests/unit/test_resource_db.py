"""Tests for resource and tag database operations."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from flow.database.resources import ResourceDB
from flow.models import Resource, Tag


@pytest.fixture
def temp_db_path() -> Path:
    """Temporary SQLite path (cleaned up after test)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink(missing_ok=True)


@pytest.fixture
def resource_db(temp_db_path: Path) -> ResourceDB:
    """Initialized ResourceDB with temp path."""
    db = ResourceDB(temp_db_path)
    db.init_db()
    return db


@pytest.fixture
def sample_resource() -> Resource:
    """Sample resource for tests."""
    return Resource(
        id="test-resource-1",
        content_type="url",
        source="https://example.com/docs",
        title="Example Docs",
        summary="Documentation for example API",
        tags=["api", "docs", "example"],
    )


@pytest.fixture
def sample_tag() -> Tag:
    """Sample tag for tests."""
    return Tag(
        name="api",
        aliases=["api-design", "rest-api"],
        usage_count=5,
    )


class TestResourceCRUD:
    """Tests for resource CRUD operations."""

    def test_insert_and_get_resource(self, resource_db, sample_resource):
        """Resource can be inserted and retrieved."""
        resource_db.insert_resource(sample_resource)

        retrieved = resource_db.get_resource(sample_resource.id)

        assert retrieved is not None
        assert retrieved.id == sample_resource.id
        assert retrieved.source == sample_resource.source
        assert retrieved.tags == sample_resource.tags

    def test_get_resource_by_source(self, resource_db, sample_resource):
        """Resource can be retrieved by source."""
        resource_db.insert_resource(sample_resource)

        retrieved = resource_db.get_resource_by_source(sample_resource.source)

        assert retrieved is not None
        assert retrieved.id == sample_resource.id

    def test_get_nonexistent_resource(self, resource_db):
        """Getting nonexistent resource returns None."""
        result = resource_db.get_resource("nonexistent")
        assert result is None

    def test_update_resource(self, resource_db, sample_resource):
        """Resource can be updated."""
        resource_db.insert_resource(sample_resource)

        # Update the resource
        updated = sample_resource.model_copy(
            update={"title": "Updated Title", "tags": ["api", "updated"]}
        )
        resource_db.update_resource(updated)

        retrieved = resource_db.get_resource(sample_resource.id)
        assert retrieved.title == "Updated Title"
        assert retrieved.tags == ["api", "updated"]

    def test_delete_resource(self, resource_db, sample_resource):
        """Resource can be deleted."""
        resource_db.insert_resource(sample_resource)
        resource_db.delete_resource(sample_resource.id)

        result = resource_db.get_resource(sample_resource.id)
        assert result is None

    def test_list_resources(self, resource_db):
        """Resources can be listed."""
        resources = [
            Resource(id=f"r{i}", content_type="url", source=f"https://example.com/{i}", tags=[])
            for i in range(5)
        ]
        for r in resources:
            resource_db.insert_resource(r)

        result = resource_db.list_resources()

        assert len(result) == 5

    def test_list_resources_by_type(self, resource_db):
        """Resources can be filtered by content type."""
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=[])
        )
        resource_db.insert_resource(
            Resource(id="r2", content_type="file", source="/path/to/file", tags=[])
        )
        resource_db.insert_resource(
            Resource(id="r3", content_type="text", source="some text", tags=[])
        )

        urls = resource_db.list_resources(content_type="url")
        files = resource_db.list_resources(content_type="file")

        assert len(urls) == 1
        assert urls[0].id == "r1"
        assert len(files) == 1
        assert files[0].id == "r2"


class TestResourceTagMatching:
    """Tests for tag-based resource matching."""

    def test_find_by_single_tag(self, resource_db):
        """Resources with matching tag are found."""
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["api", "backend"])
        )
        resource_db.insert_resource(
            Resource(id="r2", content_type="url", source="https://b.com", tags=["frontend"])
        )

        results = resource_db.find_resources_by_tags(["api"])

        assert len(results) == 1
        assert results[0].id == "r1"

    def test_find_by_multiple_tags(self, resource_db):
        """Resources matching any of the given tags are found."""
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["api"])
        )
        resource_db.insert_resource(
            Resource(id="r2", content_type="url", source="https://b.com", tags=["backend"])
        )
        resource_db.insert_resource(
            Resource(id="r3", content_type="url", source="https://c.com", tags=["frontend"])
        )

        results = resource_db.find_resources_by_tags(["api", "backend"])

        assert len(results) == 2
        ids = [r.id for r in results]
        assert "r1" in ids
        assert "r2" in ids

    def test_sorted_by_match_count(self, resource_db):
        """Results are sorted by number of matching tags."""
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["api"])
        )
        resource_db.insert_resource(
            Resource(id="r2", content_type="url", source="https://b.com", tags=["api", "backend", "docs"])
        )

        results = resource_db.find_resources_by_tags(["api", "backend", "docs"])

        # r2 should be first (3 matches) over r1 (1 match)
        assert results[0].id == "r2"

    def test_empty_tags_returns_empty(self, resource_db):
        """Empty tag list returns empty results."""
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["api"])
        )

        results = resource_db.find_resources_by_tags([])

        assert results == []


class TestTagCRUD:
    """Tests for tag CRUD operations."""

    def test_insert_and_get_tag(self, resource_db, sample_tag):
        """Tag can be inserted and retrieved."""
        resource_db.insert_tag(sample_tag)

        retrieved = resource_db.get_tag(sample_tag.name)

        assert retrieved is not None
        assert retrieved.name == sample_tag.name
        assert retrieved.usage_count == sample_tag.usage_count
        assert retrieved.aliases == sample_tag.aliases

    def test_get_nonexistent_tag(self, resource_db):
        """Getting nonexistent tag returns None."""
        result = resource_db.get_tag("nonexistent")
        assert result is None

    def test_update_tag(self, resource_db, sample_tag):
        """Tag can be updated."""
        resource_db.insert_tag(sample_tag)

        updated = sample_tag.model_copy(update={"usage_count": 10})
        resource_db.update_tag(updated)

        retrieved = resource_db.get_tag(sample_tag.name)
        assert retrieved.usage_count == 10

    def test_increment_tag_usage_existing(self, resource_db, sample_tag):
        """Usage count is incremented for existing tag."""
        resource_db.insert_tag(sample_tag)
        original_count = sample_tag.usage_count

        resource_db.increment_tag_usage(sample_tag.name)

        retrieved = resource_db.get_tag(sample_tag.name)
        assert retrieved.usage_count == original_count + 1

    def test_increment_tag_usage_creates_new(self, resource_db):
        """Incrementing nonexistent tag creates it."""
        resource_db.increment_tag_usage("new-tag")

        retrieved = resource_db.get_tag("new-tag")
        assert retrieved is not None
        assert retrieved.usage_count == 1

    def test_decrement_tag_usage(self, resource_db, sample_tag):
        """Usage count is decremented."""
        resource_db.insert_tag(sample_tag)

        resource_db.decrement_tag_usage(sample_tag.name)

        retrieved = resource_db.get_tag(sample_tag.name)
        assert retrieved.usage_count == sample_tag.usage_count - 1

    def test_decrement_tag_usage_floors_at_zero(self, resource_db):
        """Usage count doesn't go below zero."""
        resource_db.insert_tag(Tag(name="test", usage_count=0))

        resource_db.decrement_tag_usage("test")

        retrieved = resource_db.get_tag("test")
        assert retrieved.usage_count == 0

    def test_list_tags_sorted_by_usage(self, resource_db):
        """Tags are listed sorted by usage count."""
        resource_db.insert_tag(Tag(name="low", usage_count=1))
        resource_db.insert_tag(Tag(name="high", usage_count=100))
        resource_db.insert_tag(Tag(name="mid", usage_count=50))

        tags = resource_db.list_tags()

        assert tags[0].name == "high"
        assert tags[1].name == "mid"
        assert tags[2].name == "low"

    def test_get_tag_names(self, resource_db):
        """Tag names can be retrieved as simple list."""
        resource_db.insert_tag(Tag(name="api", usage_count=10))
        resource_db.insert_tag(Tag(name="backend", usage_count=5))

        names = resource_db.get_tag_names()

        assert "api" in names
        assert "backend" in names
        assert names[0] == "api"  # Sorted by usage


class TestTagMerging:
    """Tests for tag merging operations."""

    def test_merge_updates_resources(self, resource_db):
        """Merging tags updates all resources with old tag."""
        resource_db.insert_tag(Tag(name="old-tag", usage_count=2))
        resource_db.insert_tag(Tag(name="new-tag", usage_count=3))
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["old-tag", "other"])
        )
        resource_db.insert_resource(
            Resource(id="r2", content_type="url", source="https://b.com", tags=["old-tag"])
        )

        updated_count = resource_db.merge_tags("old-tag", "new-tag")

        assert updated_count == 2

        r1 = resource_db.get_resource("r1")
        assert "new-tag" in r1.tags
        assert "old-tag" not in r1.tags

    def test_merge_deletes_old_tag(self, resource_db):
        """Merged tag is deleted."""
        resource_db.insert_tag(Tag(name="old-tag", usage_count=2))
        resource_db.insert_tag(Tag(name="new-tag", usage_count=3))

        resource_db.merge_tags("old-tag", "new-tag")

        assert resource_db.get_tag("old-tag") is None

    def test_merge_updates_usage_count(self, resource_db):
        """New tag's usage count includes old tag's count."""
        resource_db.insert_tag(Tag(name="old-tag", usage_count=5))
        resource_db.insert_tag(Tag(name="new-tag", usage_count=3))

        resource_db.merge_tags("old-tag", "new-tag")

        new_tag = resource_db.get_tag("new-tag")
        assert new_tag.usage_count == 8  # 5 + 3

    def test_merge_no_duplicate_tags_in_resource(self, resource_db):
        """Merging doesn't create duplicate tags in resource."""
        resource_db.insert_tag(Tag(name="old-tag", usage_count=1))
        resource_db.insert_tag(Tag(name="new-tag", usage_count=1))
        resource_db.insert_resource(
            Resource(id="r1", content_type="url", source="https://a.com", tags=["old-tag", "new-tag"])
        )

        resource_db.merge_tags("old-tag", "new-tag")

        r1 = resource_db.get_resource("r1")
        assert r1.tags.count("new-tag") == 1
