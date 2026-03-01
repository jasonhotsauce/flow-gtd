"""Obsidian vault resource store provider."""

from __future__ import annotations

import json
import re
from pathlib import Path

from flow.core.resources.models import HealthCheckResult, ResourceRecord, SemanticHit
from flow.utils.obsidian_cli import ObsidianCLI


class ObsidianVaultResourceStore:
    """Resource store provider writing resource notes into an Obsidian vault."""

    def __init__(
        self,
        vault_path: str | Path,
        *,
        notes_dir: str = "flow/resources",
        cli: ObsidianCLI | None = None,
    ) -> None:
        self._vault_path = str(vault_path)
        self._notes_dir = notes_dir.strip("/") or "flow/resources"
        self._cli = cli or ObsidianCLI()
        self._index_path = Path(self._vault_path) / ".flow" / "resources_index.json"
        self._resources = self._load_index()

    def save_resource(self, resource: ResourceRecord) -> ResourceRecord:
        note_path = f"{self._notes_dir}/{resource.id}.md"
        content = self._render_note(resource)
        result = self._cli.create_note(
            vault_path=self._vault_path,
            note_path=note_path,
            content=content,
        )
        if not result.ok:
            raise RuntimeError(result.message or "Failed to save resource to Obsidian vault")
        self._resources[resource.id] = resource
        self._persist_index()
        return resource

    def get_resource(self, resource_id: str) -> ResourceRecord | None:
        return self._resources.get(resource_id)

    def list_resources(
        self, *, content_type: str | None = None, limit: int = 100
    ) -> list[ResourceRecord]:
        values = list(self._resources.values())
        if content_type is not None:
            values = [item for item in values if item.content_type == content_type]
        return values[:limit]

    def search_by_tags(self, tags: list[str], *, limit: int = 100) -> list[ResourceRecord]:
        if not tags:
            return []
        tag_set = set(tags)
        matches = [
            item
            for item in self._resources.values()
            if tag_set.intersection(item.tags)
        ]
        matches.sort(key=lambda item: len(tag_set.intersection(item.tags)), reverse=True)
        return matches[:limit]

    def semantic_search(self, query_text: str, *, top_k: int = 3) -> list[SemanticHit]:
        query_tokens = _tokenize(query_text)
        if not query_tokens:
            return []
        hits: list[SemanticHit] = []
        for resource in self._resources.values():
            text = " ".join(
                part
                for part in (
                    resource.title or "",
                    resource.summary or "",
                    resource.raw_content or "",
                    resource.source,
                    " ".join(resource.tags),
                )
                if part
            )
            resource_tokens = _tokenize(text)
            score = _jaccard(query_tokens, resource_tokens)
            if score <= 0:
                continue
            snippet = (resource.summary or resource.raw_content or resource.source)[:200]
            hits.append(
                SemanticHit(
                    resource_id=resource.id,
                    score=score,
                    title=resource.title,
                    source=resource.source,
                    snippet=snippet,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def list_tags(self) -> list[str]:
        names: set[str] = set()
        for resource in self._resources.values():
            names.update(resource.tags)
        return sorted(names)

    def health_check(self) -> HealthCheckResult:
        result = self._cli.health_check()
        return HealthCheckResult(ok=result.ok, message=result.message)

    def _render_note(self, resource: ResourceRecord) -> str:
        tags = "\n".join(f"  - {tag}" for tag in resource.tags)
        frontmatter = (
            "---\n"
            f"id: {resource.id}\n"
            f"content_type: {resource.content_type}\n"
            f"source: {resource.source}\n"
            f"created_at: {resource.created_at.isoformat()}\n"
            "tags:\n"
            f"{tags}\n"
            "---\n\n"
        )
        title = f"# {resource.title}\n\n" if resource.title else ""
        summary = f"{resource.summary}\n\n" if resource.summary else ""
        body = resource.raw_content or ""
        return f"{frontmatter}{title}{summary}{body}".rstrip() + "\n"

    def _load_index(self) -> dict[str, ResourceRecord]:
        if not self._index_path.exists():
            return {}
        try:
            payload = json.loads(self._index_path.read_text())
        except (OSError, ValueError):
            return {}
        if not isinstance(payload, list):
            return {}
        items: dict[str, ResourceRecord] = {}
        for raw in payload:
            try:
                record = ResourceRecord.model_validate(raw)
            except Exception:
                continue
            items[record.id] = record
        return items

    def _persist_index(self) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [resource.model_dump(mode="json") for resource in self._resources.values()]
        self._index_path.write_text(json.dumps(payload, indent=2))


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a.intersection(b))
    if intersection == 0:
        return 0.0
    return intersection / len(a.union(b))
