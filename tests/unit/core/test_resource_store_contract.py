"""Contract tests for resource store abstraction."""

from __future__ import annotations

from datetime import datetime, timezone

from flow.core.resources.models import HealthCheckResult, ResourceRecord, SemanticHit
from flow.core.resources.store import ResourceStore


def test_resource_store_protocol_has_required_methods() -> None:
    required = [
        "save_resource",
        "get_resource",
        "list_resources",
        "search_by_tags",
        "semantic_search",
        "list_tags",
        "health_check",
    ]
    for name in required:
        assert hasattr(ResourceStore, name)


def test_resource_record_round_trip_to_domain_model() -> None:
    record = ResourceRecord(
        id="res-1",
        content_type="url",
        source="https://example.com",
        title="Example",
        summary="Summary",
        tags=["docs", "api"],
        created_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
        raw_content="raw",
    )

    domain_model = record.to_domain_model()
    restored = ResourceRecord.from_domain_model(domain_model)

    assert restored == record


def test_semantic_hit_and_health_check_defaults() -> None:
    hit = SemanticHit(
        resource_id="res-1",
        score=0.95,
        title="Example",
        source="https://example.com",
    )
    health = HealthCheckResult(ok=True)

    assert hit.score == 0.95
    assert hit.resource_id == "res-1"
    assert health.ok is True
    assert health.message is None
