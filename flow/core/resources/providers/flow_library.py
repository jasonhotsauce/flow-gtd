"""Flow-managed resource store provider backed by ResourceDB."""

from __future__ import annotations

from flow.core.resources.models import HealthCheckResult, ResourceRecord, SemanticHit
from flow.database.resources import ResourceDB


class FlowLibraryResourceStore:
    """Resource store provider using Flow's local SQLite resource database."""

    def __init__(self, resource_db: ResourceDB) -> None:
        self._resource_db = resource_db

    def save_resource(self, resource: ResourceRecord) -> ResourceRecord:
        domain = resource.to_domain_model()
        existing = self._resource_db.get_resource(resource.id)
        if existing is None:
            self._resource_db.insert_resource(domain)
        else:
            self._resource_db.update_resource(domain)

        for tag in resource.tags:
            self._resource_db.increment_tag_usage(tag)

        return resource

    def get_resource(self, resource_id: str) -> ResourceRecord | None:
        resource = self._resource_db.get_resource(resource_id)
        if resource is None:
            return None
        return ResourceRecord.from_domain_model(resource)

    def list_resources(
        self, *, content_type: str | None = None, limit: int = 100
    ) -> list[ResourceRecord]:
        resources = self._resource_db.list_resources(content_type=content_type, limit=limit)
        return [ResourceRecord.from_domain_model(item) for item in resources]

    def search_by_tags(self, tags: list[str], *, limit: int = 100) -> list[ResourceRecord]:
        resources = self._resource_db.find_resources_by_tags(tags, limit=limit)
        return [ResourceRecord.from_domain_model(item) for item in resources]

    def semantic_search(self, query_text: str, *, top_k: int = 3) -> list[SemanticHit]:
        # Semantic retrieval for Flow library remains in the existing RAG path.
        return []

    def list_tags(self) -> list[str]:
        return self._resource_db.get_tag_names()

    def health_check(self) -> HealthCheckResult:
        try:
            self._resource_db.list_resources(limit=1)
        except Exception as exc:
            return HealthCheckResult(ok=False, message=str(exc))
        return HealthCheckResult(ok=True)
