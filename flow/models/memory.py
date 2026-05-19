"""Memory domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

MemoryKind = Literal[
    "explicit_preference",
    "accepted_edit_pattern",
    "planning_preference",
    "notification_preference",
    "project_context",
]
MemoryScope = Literal["global", "project", "task"]


class MemoryEntry(BaseModel):
    """Inspectable memory that can influence planning and assistant behavior."""

    id: str
    kind: MemoryKind
    scope: MemoryScope
    scope_ref: str | None = None
    value: str
    source: str
    confidence: float = 1.0
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_confirmed_at: datetime | None = None
