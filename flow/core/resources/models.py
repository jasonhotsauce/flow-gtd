"""Backend-agnostic models for resource store providers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from flow.models import Resource


class ResourceRecord(BaseModel):
    """Canonical resource representation across storage providers."""

    id: str
    content_type: str
    source: str
    title: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_content: str | None = None
    backend_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain_model(cls, resource: Resource) -> "ResourceRecord":
        return cls(
            id=resource.id,
            content_type=resource.content_type,
            source=resource.source,
            title=resource.title,
            summary=resource.summary,
            tags=list(resource.tags),
            created_at=resource.created_at,
            raw_content=resource.raw_content,
        )

    def to_domain_model(self) -> Resource:
        return Resource(
            id=self.id,
            content_type=self.content_type,
            source=self.source,
            title=self.title,
            summary=self.summary,
            tags=list(self.tags),
            created_at=self.created_at,
            raw_content=self.raw_content,
        )


class SemanticHit(BaseModel):
    """Semantic retrieval result normalized across providers."""

    resource_id: str
    score: float
    title: str | None = None
    source: str | None = None
    snippet: str | None = None


class HealthCheckResult(BaseModel):
    """Provider health check response."""

    ok: bool
    message: str | None = None
