"""Polymorphic schema for Inbox / Action / Project / Reference items."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ItemType = Literal["inbox", "action", "project", "reference"]
ItemStatus = Literal["active", "done", "waiting", "someday", "archived"]


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
