"""Resource store contract for provider implementations."""

from __future__ import annotations

from typing import Protocol

from .models import HealthCheckResult, ResourceRecord, SemanticHit


class ResourceStore(Protocol):
    """Provider contract for Flow resource persistence and retrieval."""

    def save_resource(self, resource: ResourceRecord) -> ResourceRecord:
        """Persist a resource and return the saved record."""

    def get_resource(self, resource_id: str) -> ResourceRecord | None:
        """Fetch a resource by unique ID."""

    def list_resources(
        self, *, content_type: str | None = None, limit: int = 100
    ) -> list[ResourceRecord]:
        """List resources with optional content-type filtering."""

    def search_by_tags(self, tags: list[str], *, limit: int = 100) -> list[ResourceRecord]:
        """Search resources by one or more tags."""

    def semantic_search(self, query_text: str, *, top_k: int = 3) -> list[SemanticHit]:
        """Search semantically related resources for query text."""

    def list_tags(self) -> list[str]:
        """List known tags."""

    def health_check(self) -> HealthCheckResult:
        """Validate provider readiness and return status."""
