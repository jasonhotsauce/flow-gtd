"""Resource lookup and index queue service operations."""

from __future__ import annotations

from flow.database.resources import ResourceDB
from flow.models import Resource


class ResourceService:
    """Resource retrieval and queue orchestration."""

    def __init__(self, resource_db: ResourceDB) -> None:
        self._resource_db = resource_db

    def get_resources_by_tags(self, tags: list[str]) -> list[Resource]:
        if not tags:
            return []
        return self._resource_db.find_resources_by_tags(tags)

    def get_tag_names(self) -> list[str]:
        return self._resource_db.get_tag_names()

    def increment_tag_usage(self, tag: str) -> None:
        self._resource_db.increment_tag_usage(tag)
