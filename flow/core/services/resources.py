"""Resource lookup and index queue service operations."""

from __future__ import annotations

from flow.core.resources.store import ResourceStore
from flow.models import Resource


class ResourceService:
    """Resource retrieval and queue orchestration."""

    def __init__(self, store: ResourceStore) -> None:
        self._store = store

    def get_resources_by_tags(self, tags: list[str]) -> list[Resource]:
        if not tags:
            return []
        records = self._store.search_by_tags(tags)
        return [record.to_domain_model() for record in records]

    def get_tag_names(self) -> list[str]:
        return self._store.list_tags()
