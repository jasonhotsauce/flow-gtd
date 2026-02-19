"""Weekly-review service operations."""

from __future__ import annotations

from flow.database.sqlite import SqliteDB
from flow.models import Item


class ReviewService:
    """Read-model operations for weekly review flows."""

    def __init__(self, db: SqliteDB) -> None:
        self._db = db

    def get_stale(self, days: int = 14) -> list[Item]:
        return self._db.list_stale(days=days)

    def get_someday_suggestions(self) -> list[Item]:
        return self._db.list_someday()

    def weekly_report(self, days: int = 7) -> str:
        done = self._db.list_done_since(days=days)
        lines = [
            "# Flow Weekly Report",
            "",
            f"**Completed this week:** {len(done)} items",
            "",
            "## Done",
            "",
        ]
        for item in done:
            lines.append(f"- {item.title[:80]}{'...' if len(item.title) > 80 else ''}")
        return "\n".join(lines)
