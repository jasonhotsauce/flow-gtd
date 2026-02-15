"""Vector store interfaces for local semantic retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class VectorHit:
    """Semantic retrieval hit."""

    resource_id: str
    score: float
    title: str
    snippet: str
    source: str


class VectorStore(Protocol):
    """Protocol for local vector stores."""

    def upsert_resource(
        self,
        resource_id: str,
        title: str,
        text: str,
        source: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        ...

    def query(self, query_text: str, top_k: int = 3) -> list[VectorHit]:
        ...

    def delete_resource(self, resource_id: str) -> None:
        ...
