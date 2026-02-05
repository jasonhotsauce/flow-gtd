"""Resource and tag database operations (SQLite).

This module provides CRUD operations for the resources and tags tables,
supporting the tag-based resource matching system.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flow.models import ContentType, Resource, Tag


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO string."""
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string, returning None for invalid input."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class ResourceDB:
    """SQLite wrapper for resources and tags tables."""

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def init_db(self) -> None:
        """Create resources and tags tables if they do not exist."""
        with sqlite3.connect(self._path) as conn:
            # Resources table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    content_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    tags TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    raw_content TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(content_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resources_created ON resources(created_at)"
            )

            # Tags table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    name TEXT PRIMARY KEY,
                    aliases TEXT,
                    usage_count INTEGER DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tags_usage ON tags(usage_count DESC)"
            )
            conn.commit()

    # ---- Resource CRUD ----

    def insert_resource(self, resource: Resource) -> None:
        """Insert a new resource."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO resources (id, content_type, source, title, summary, 
                                       tags, created_at, raw_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource.id,
                    resource.content_type,
                    resource.source,
                    resource.title,
                    resource.summary,
                    json.dumps(resource.tags),
                    _iso(resource.created_at),
                    resource.raw_content,
                ),
            )
            conn.commit()

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a resource by ID."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM resources WHERE id = ?", (resource_id,)
            ).fetchone()
        return _row_to_resource(row) if row else None

    def get_resource_by_source(self, source: str) -> Optional[Resource]:
        """Get a resource by source (URL, filepath, or text)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM resources WHERE source = ?", (source,)
            ).fetchone()
        return _row_to_resource(row) if row else None

    def update_resource(self, resource: Resource) -> None:
        """Update an existing resource."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE resources SET content_type=?, source=?, title=?, summary=?,
                                     tags=?, created_at=?, raw_content=?
                WHERE id = ?
                """,
                (
                    resource.content_type,
                    resource.source,
                    resource.title,
                    resource.summary,
                    json.dumps(resource.tags),
                    _iso(resource.created_at),
                    resource.raw_content,
                    resource.id,
                ),
            )
            conn.commit()

    def delete_resource(self, resource_id: str) -> None:
        """Delete a resource by ID."""
        with sqlite3.connect(self._path) as conn:
            conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
            conn.commit()

    def list_resources(
        self,
        content_type: Optional[ContentType] = None,
        limit: int = 100,
    ) -> list[Resource]:
        """List resources, optionally filtered by content type."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            if content_type:
                rows = conn.execute(
                    "SELECT * FROM resources WHERE content_type = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (content_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM resources ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_row_to_resource(r) for r in rows]

    def find_resources_by_tags(
        self, tags: list[str], limit: int = 100
    ) -> list[Resource]:
        """Find resources that share at least one tag with the given list.

        Uses SQLite json_each to filter and order in the database; never
        loads the full table.

        Args:
            tags: List of tag names to match against.
            limit: Maximum number of resources to return (default 100).

        Returns:
            List of resources with at least one matching tag, ordered by
            number of matching tags (most matches first).
        """
        if not tags:
            return []

        placeholders = ",".join("?" * len(tags))
        # Subquery counts how many of the resource's tags are in our list.
        # Filter to match_count > 0, order by match_count DESC, then limit.
        params = tags + tags + [limit]
        query = f"""
            SELECT * FROM resources r
            WHERE (
                SELECT COUNT(*) FROM json_each(r.tags)
                WHERE json_each.value IN ({placeholders})
            ) > 0
            ORDER BY (
                SELECT COUNT(*) FROM json_each(r.tags)
                WHERE json_each.value IN ({placeholders})
            ) DESC
            LIMIT ?
        """

        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [_row_to_resource(r) for r in rows]

    # ---- Tag CRUD ----

    def insert_tag(self, tag: Tag) -> None:
        """Insert a new tag."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO tags (name, aliases, usage_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    tag.name,
                    json.dumps(tag.aliases),
                    tag.usage_count,
                    _iso(tag.created_at),
                ),
            )
            conn.commit()

    def get_tag(self, name: str) -> Optional[Tag]:
        """Get a tag by name."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tags WHERE name = ?", (name,)
            ).fetchone()
        return _row_to_tag(row) if row else None

    def update_tag(self, tag: Tag) -> None:
        """Update an existing tag."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE tags SET aliases=?, usage_count=?, created_at=?
                WHERE name = ?
                """,
                (
                    json.dumps(tag.aliases),
                    tag.usage_count,
                    _iso(tag.created_at),
                    tag.name,
                ),
            )
            conn.commit()

    def increment_tag_usage(self, name: str) -> None:
        """Increment usage count for a tag. Creates tag if it doesn't exist."""
        with sqlite3.connect(self._path) as conn:
            # Try to update existing tag
            cursor = conn.execute(
                "UPDATE tags SET usage_count = usage_count + 1 WHERE name = ?",
                (name,),
            )
            if cursor.rowcount == 0:
                # Tag doesn't exist, create it
                conn.execute(
                    """
                    INSERT INTO tags (name, aliases, usage_count, created_at)
                    VALUES (?, ?, 1, ?)
                    """,
                    (name, "[]", _iso(datetime.now(timezone.utc))),
                )
            conn.commit()

    def decrement_tag_usage(self, name: str) -> None:
        """Decrement usage count for a tag."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "UPDATE tags SET usage_count = MAX(0, usage_count - 1) WHERE name = ?",
                (name,),
            )
            conn.commit()

    def list_tags(self, limit: int = 100) -> list[Tag]:
        """List all tags ordered by usage count (most used first)."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tags ORDER BY usage_count DESC, name ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_tag(r) for r in rows]

    def get_tag_names(self) -> list[str]:
        """Get all tag names as a simple list (for LLM prompts)."""
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                "SELECT name FROM tags ORDER BY usage_count DESC"
            ).fetchall()
        return [r[0] for r in rows]

    def merge_tags(self, old_name: str, new_name: str) -> int:
        """Merge old tag into new tag, updating all resources.

        Args:
            old_name: Tag to be merged (will be deleted).
            new_name: Tag to merge into (will have usage count updated).

        Returns:
            Number of resources updated.
        """
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get all resources with the old tag
            rows = conn.execute("SELECT * FROM resources").fetchall()
            updated_count = 0
            
            for row in rows:
                tags = json.loads(row["tags"] or "[]")
                if old_name in tags:
                    tags.remove(old_name)
                    if new_name not in tags:
                        tags.append(new_name)
                    conn.execute(
                        "UPDATE resources SET tags = ? WHERE id = ?",
                        (json.dumps(tags), row["id"]),
                    )
                    updated_count += 1
            
            # Update tag usage counts
            old_tag = conn.execute(
                "SELECT usage_count FROM tags WHERE name = ?", (old_name,)
            ).fetchone()
            
            if old_tag:
                old_count = old_tag[0]
                # Increment new tag by old tag's count
                conn.execute(
                    "UPDATE tags SET usage_count = usage_count + ? WHERE name = ?",
                    (old_count, new_name),
                )
                # Delete old tag
                conn.execute("DELETE FROM tags WHERE name = ?", (old_name,))
            
            conn.commit()
        
        return updated_count


def _row_to_resource(row: sqlite3.Row) -> Resource:
    """Convert database row to Resource model."""
    try:
        tags = json.loads(row["tags"] or "[]")
    except json.JSONDecodeError:
        tags = []

    return Resource(
        id=row["id"],
        content_type=row["content_type"],
        source=row["source"],
        title=row["title"],
        summary=row["summary"],
        tags=tags,
        created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
        raw_content=row["raw_content"],
    )


def _row_to_tag(row: sqlite3.Row) -> Tag:
    """Convert database row to Tag model."""
    try:
        aliases = json.loads(row["aliases"] or "[]")
    except json.JSONDecodeError:
        aliases = []

    return Tag(
        name=row["name"],
        aliases=aliases,
        usage_count=row["usage_count"] or 0,
        created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
    )
