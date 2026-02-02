"""ChromaDB wrapper for embeddings (RAG). Persistent local mode, sentence-transformers."""

import re
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_PDF_PATH_RE = re.compile(r"\S+\.pdf", re.IGNORECASE)
COLLECTION_NAME = "flow_docs"


def _contains_url_or_pdf(text: str) -> bool:
    return bool(_URL_RE.search(text) or _PDF_PATH_RE.search(text))


def _get_client(chroma_path: Path):
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    path_str = str(chroma_path.resolve())
    chroma_path.mkdir(parents=True, exist_ok=True)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=path_str)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
    )


def add_documents(
    documents: list[str],
    metadatas: Optional[list[dict[str, Any]]] = None,
    chroma_path: Optional[Path] = None,
) -> None:
    """Add document texts to ChromaDB with optional metadata (e.g. filename, source)."""
    from flow.config import get_settings

    path = chroma_path or get_settings().chroma_path
    coll = _get_client(path)
    ids = [str(uuid.uuid4()) for _ in documents]
    meta = metadatas or [{}] * len(documents)
    if len(meta) != len(documents):
        meta = [{} for _ in documents]
    coll.add(ids=ids, documents=documents, metadatas=meta)


def query(
    query_text: str,
    top_k: int = 3,
    chroma_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """
    Search ChromaDB by text. Returns list of dicts with keys:
    id, document (snippet), metadata, distance (similarity score).
    """
    from flow.config import get_settings

    path = chroma_path or get_settings().chroma_path
    if not path.exists():
        return []
    coll = _get_client(path)
    result = coll.query(
        query_texts=[query_text],
        n_results=min(top_k, 10),
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict[str, Any]] = []
    if result["ids"] and result["ids"][0]:
        for i, doc_id in enumerate(result["ids"][0]):
            doc = (result["documents"][0][i]) if result["documents"] else ""
            meta = (result["metadatas"][0][i]) if result["metadatas"] else {}
            has_dist = result.get("distances") and result["distances"][0]
            dist = (result["distances"][0][i]) if has_dist else None
            out.append(
                {
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta or {},
                    "distance": dist,
                }
            )
    return out


def schedule_auto_index(text: str, chroma_path: Optional[Path] = None) -> None:
    """
    If text contains a URL or path to PDF, schedule async fetch + embed + add to ChromaDB.
    Must not block caller.
    """
    if not _contains_url_or_pdf(text):
        return

    def _run() -> None:
        # Minimal auto-index: extract URL or path and add raw text as single doc
        url_match = _URL_RE.search(text)
        path_match = _PDF_PATH_RE.search(text)
        try:
            if url_match:
                url = url_match.group(0).strip()
                add_documents(
                    [text],
                    metadatas=[{"source": "url", "url": url}],
                    chroma_path=chroma_path,
                )
            elif path_match:
                p = path_match.group(0).strip()
                add_documents(
                    [text],
                    metadatas=[{"source": "file", "path": p}],
                    chroma_path=chroma_path,
                )
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
