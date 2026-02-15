"""ChromaDB-backed local vector store."""

from __future__ import annotations

import inspect
import logging
import math
from pathlib import Path
from typing import Any, Callable

from .vector_store import VectorHit

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """Persistent local Chroma vector store."""

    def __init__(self, store_path: Path, collection_name: str = "flow_resources") -> None:
        self._store_path = Path(store_path)
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None
        self._encoder: Any = None
        self._available = self._init_backend()

    @property
    def available(self) -> bool:
        return self._available

    def _init_backend(self) -> bool:
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            self._patch_chroma_posthog_capture()
            self._store_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self._store_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name
            )
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            return True
        except Exception:
            self._client = None
            self._collection = None
            self._encoder = None
            return False

    @staticmethod
    def _needs_posthog_capture_compat(capture_fn: Callable[..., Any]) -> bool:
        """Detect posthog APIs that only accept `event` as positional input."""
        try:
            signature = inspect.signature(capture_fn)
        except (TypeError, ValueError):
            return False

        if any(
            param.kind is inspect.Parameter.VAR_POSITIONAL
            for param in signature.parameters.values()
        ):
            return False

        positional_count = sum(
            1
            for param in signature.parameters.values()
            if param.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
        return positional_count <= 1

    @staticmethod
    def _make_posthog_capture_compat(
        capture_fn: Callable[..., Any],
        posthog_module: Any | None = None,
    ) -> Callable[..., Any]:
        """Wrap capture(event, **kwargs) so Chroma legacy calls still work."""

        def _capture_compat(*args: Any, **kwargs: Any) -> Any:
            if posthog_module is not None and getattr(posthog_module, "disabled", False):
                return None

            if len(args) >= 2:
                distinct_id = args[0]
                event_name = args[1]
                properties = args[2] if len(args) >= 3 and isinstance(args[2], dict) else None
                kwargs.setdefault("distinct_id", distinct_id)
                if properties is not None:
                    kwargs.setdefault("properties", properties)
                api_key = (
                    getattr(posthog_module, "project_api_key", None)
                    if posthog_module is not None
                    else None
                )
                if api_key:
                    kwargs.setdefault("api_key", api_key)
                return capture_fn(event_name, **kwargs)
            return capture_fn(*args, **kwargs)

        return _capture_compat

    def _patch_chroma_posthog_capture(self) -> None:
        """Patch incompatible posthog API used by older Chroma telemetry code."""
        try:
            import chromadb.telemetry.product.posthog as chroma_posthog
        except Exception:
            return

        capture_fn = getattr(chroma_posthog.posthog, "capture", None)
        if capture_fn is None or not callable(capture_fn):
            return
        if not self._needs_posthog_capture_compat(capture_fn):
            return

        chroma_posthog.posthog.capture = self._make_posthog_capture_compat(
            capture_fn, posthog_module=chroma_posthog.posthog
        )
        logger.debug("Installed Chroma/PostHog capture compatibility shim.")

    def upsert_resource(
        self,
        resource_id: str,
        title: str,
        text: str,
        source: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        if not self._available:
            return
        payload = (text or "").strip()
        if not payload:
            payload = title or source
        if not payload:
            return
        emb = self._encoder.encode(payload).tolist()
        meta = dict(metadata or {})
        meta.setdefault("title", title or source)
        meta.setdefault("source", source)
        meta.setdefault("snippet", payload[:300])
        self._collection.upsert(
            ids=[resource_id],
            embeddings=[emb],
            documents=[payload[:4000]],
            metadatas=[meta],
        )

    def query(self, query_text: str, top_k: int = 3) -> list[VectorHit]:
        if not self._available or not query_text.strip():
            return []
        emb = self._encoder.encode(query_text).tolist()
        result = self._collection.query(
            query_embeddings=[emb],
            n_results=max(1, top_k),
            include=["metadatas", "distances", "documents"],
        )
        ids = result.get("ids", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        docs = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[VectorHit] = []
        for idx, resource_id in enumerate(ids):
            meta = metas[idx] if idx < len(metas) and metas[idx] else {}
            doc = docs[idx] if idx < len(docs) and docs[idx] else ""
            distance = distances[idx] if idx < len(distances) else 1.0
            score = max(0.0, 1.0 - float(distance))
            if math.isnan(score):
                score = 0.0
            hits.append(
                VectorHit(
                    resource_id=resource_id,
                    score=score,
                    title=str(meta.get("title", "Untitled")),
                    snippet=str(meta.get("snippet", doc[:280])),
                    source=str(meta.get("source", "")),
                )
            )
        return hits

    def delete_resource(self, resource_id: str) -> None:
        if not self._available:
            return
        self._collection.delete(ids=[resource_id])
