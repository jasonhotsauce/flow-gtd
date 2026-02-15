"""Local semantic indexing and retrieval service."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Optional

from flow.config import get_settings
from flow.database.chroma_store import ChromaVectorStore
from flow.database.resources import ResourceDB
from flow.database.sqlite import SqliteDB
from flow.database.vector_store import VectorHit

logger = logging.getLogger(__name__)

_worker_lock = Lock()


class RAGService:
    """Coordinates durable indexing jobs and semantic retrieval."""

    def __init__(
        self,
        db: SqliteDB,
        resource_db: ResourceDB,
        store_path: Optional[Path] = None,
    ) -> None:
        self._db = db
        self._resource_db = resource_db
        settings = get_settings()
        base_path = store_path or (settings.db_path.parent / "chroma")
        self._store_path = base_path
        self._store: Optional[ChromaVectorStore] = None
        self._store_lock = Lock()
        self._enabled = settings.rag_enabled

    def _ensure_store(self) -> Optional[ChromaVectorStore]:
        """Lazily initialize vector backend to avoid startup UI blocking."""
        if not self._enabled:
            return None
        if self._store is not None:
            return self._store
        with self._store_lock:
            if self._store is None:
                self._store = ChromaVectorStore(self._store_path)
        return self._store

    @property
    def available(self) -> bool:
        store = self._ensure_store()
        return bool(store and store.available)

    def enqueue_resource_index(
        self,
        *,
        resource_id: str,
        content_type: str,
        source: str,
        title: Optional[str],
        summary: Optional[str],
    ) -> str:
        return self._db.enqueue_index_job(
            resource_id=resource_id,
            content_type=content_type,
            source=source,
            title=title,
            summary=summary,
        )

    def process_pending_jobs(self, limit: int = 20) -> int:
        """Process pending queue jobs in FIFO order."""
        store = self._ensure_store()
        if not store or not store.available:
            return 0
        processed = 0
        jobs = self._db.list_index_jobs(status="pending", limit=limit)
        for job in jobs:
            job_id = str(job["id"])
            try:
                self._db.update_index_job_status(job_id, status="processing")
                resource = self._resource_db.get_resource(str(job["resource_id"]))
                title = str(job.get("title") or "")
                source = str(job.get("source") or "")
                if resource:
                    title = resource.title or title
                    source = resource.source or source
                    text = self._build_index_text(
                        title=resource.title,
                        summary=resource.summary,
                        source=resource.source,
                        raw_content=resource.raw_content,
                    )
                else:
                    text = self._build_index_text(
                        title=title,
                        summary=str(job.get("summary") or ""),
                        source=source,
                    )
                store.upsert_resource(
                    resource_id=str(job["resource_id"]),
                    title=title or source,
                    text=text,
                    source=source,
                    metadata={"content_type": str(job.get("content_type") or "text")},
                )
                self._db.update_index_job_status(job_id, status="done")
                processed += 1
            except Exception as exc:
                logger.warning("Failed to process index job %s: %s", job_id, exc)
                self._db.update_index_job_status(job_id, status="error", error=str(exc))
        return processed

    def process_pending_jobs_once(self, limit: int = 20) -> int:
        """Thread-safe single-worker queue processor."""
        with _worker_lock:
            return self.process_pending_jobs(limit=limit)

    def semantic_search(self, query_text: str, top_k: int = 3) -> list[VectorHit]:
        store = self._ensure_store()
        if not store or not store.available:
            return []
        return store.query(query_text=query_text, top_k=top_k)

    @staticmethod
    def _build_index_text(
        *,
        title: Optional[str],
        summary: Optional[str],
        source: Optional[str],
        raw_content: Optional[str] = None,
    ) -> str:
        parts = []
        if title:
            parts.append(title)
        if summary:
            parts.append(summary)
        if raw_content:
            parts.append(raw_content[:2000])
        if source:
            parts.append(source)
        return "\n".join(parts)
