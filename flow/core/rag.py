"""Semantic search: link tasks to docs (RAG)."""

from pathlib import Path
from typing import Any, Optional

from flow.database import vectors


def query(
    task_title: str,
    top_k: int = 3,
    chroma_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """
    Given task title (or short text), embed and search ChromaDB.
    Returns list of dicts: filename (or source), similarity score, snippet.
    """
    raw = vectors.query(query_text=task_title, top_k=top_k, chroma_path=chroma_path)
    out: list[dict[str, Any]] = []
    for r in raw:
        meta = r.get("metadata") or {}
        filename = meta.get("filename") or meta.get("path") or meta.get("url") or "doc"
        snippet = (r.get("document") or "")[:300]
        if len((r.get("document") or "")) > 300:
            snippet += "..."
        # ChromaDB returns distance (lower = more similar); convert to simple score for display
        dist = r.get("distance")
        score = 1.0 / (1.0 + dist) if dist is not None else None
        out.append({
            "filename": filename,
            "score": score,
            "snippet": snippet,
            "metadata": meta,
        })
    return out
