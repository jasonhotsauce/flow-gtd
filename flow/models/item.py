"""Polymorphic schema for Inbox / Action / Project / Reference items."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ItemType = Literal["inbox", "action", "project", "reference"]
ItemStatus = Literal["active", "done", "waiting", "someday", "archived"]
ContentType = Literal["url", "file", "text"]


class Resource(BaseModel):
    """A saved resource (URL, file, or text) with tags for matching to tasks.

    Resources are stored in the `resources` SQLite table and matched to tasks
    via shared tags.
    """

    id: str = Field(description="Unique identifier (UUID)")
    content_type: ContentType = Field(description="Type of content: url, file, or text")
    source: str = Field(description="URL, filepath, or raw text")
    title: Optional[str] = Field(None, description="Resource title")
    summary: Optional[str] = Field(None, description="Short description or preview")
    tags: list[str] = Field(default_factory=list, description="List of tag names")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the resource was saved",
    )
    raw_content: Optional[str] = Field(None, description="Optional cached full content")


class Tag(BaseModel):
    """A tag in the vocabulary for organizing resources and tasks.

    Tags are stored in the `tags` SQLite table with usage tracking.
    """

    name: str = Field(description="Tag name (lowercase, hyphenated)")
    aliases: list[str] = Field(
        default_factory=list, description="Alternative names for this tag"
    )
    usage_count: int = Field(default=0, description="Number of times this tag is used")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the tag was created",
    )


class Item(BaseModel):
    """Single item (task, project, or reference) in the GTD system."""

    id: str
    type: ItemType
    title: str
    status: ItemStatus = "active"
    context_tags: list[str] = Field(default_factory=list)
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    due_date: Optional[datetime] = None
    meta_payload: dict[str, Any] = Field(default_factory=dict)
    original_ek_id: Optional[str] = None
    estimated_duration: Optional[int] = None  # Duration in minutes for Focus Mode
    updated_at: Optional[datetime] = None  # Set on update; used for "completed this week"
