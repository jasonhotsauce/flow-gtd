"""Smart Dispatcher for Focus Mode: context-aware task selection."""

from typing import Optional

from flow.core.engine import Engine
from flow.database.vector_store import VectorHit
from flow.models import Item, Resource
from flow.sync.calendar import CalendarEvent, get_next_event

# Time window thresholds (in minutes)
QUICK_WIN_THRESHOLD = 30  # Below this: prioritize short tasks
DEEP_WORK_THRESHOLD = 120  # Above this: prioritize high-energy tasks
DEFAULT_TIME_WINDOW = 60  # Fallback when no calendar data


class FocusDispatcher:
    """Selects optimal task based on available time window from calendar.

    The Smart Dispatcher algorithm:
    1. Query EventKit for next calendar event
    2. Calculate available time window
    3. Select best task based on window:
       - < 30 mins: Quick Wins (short duration or @admin tag)
       - > 2 hours: Deep Work (high energy tasks)
       - Otherwise: Standard priority order
    """

    def __init__(self, engine: Optional[Engine] = None) -> None:
        """Initialize dispatcher with engine instance.

        Args:
            engine: Engine instance for database access. Creates new if None.
        """
        self._engine = engine or Engine()
        self._skipped_ids: set[str] = set()

    def get_time_window(self) -> tuple[int, Optional[str]]:
        """Get available time window until next calendar event.

        Returns:
            Tuple of (minutes_available, next_event_title).
            Falls back to DEFAULT_TIME_WINDOW if no calendar data.
        """
        event = get_next_event()
        if event is None:
            return DEFAULT_TIME_WINDOW, None
        return event.minutes_until_start, event.title

    def get_next_event(self) -> Optional[CalendarEvent]:
        """Get the next calendar event (for display purposes).

        Returns:
            CalendarEvent or None if no upcoming events.
        """
        return get_next_event()

    def select_task(self) -> Optional[Item]:
        """Select the best task based on available time window.

        Selection algorithm:
        - If window < 30 mins: Filter for short tasks (<=15 min) or @admin tags
        - If window > 120 mins: Prioritize high-energy tasks
        - Otherwise: Return first available active task

        Skipped tasks (via skip_task) are excluded from selection.

        Returns:
            Best matching Item, or None if no tasks available.
        """
        window, _ = self.get_time_window()
        actions = self._engine.next_actions()

        # Filter out skipped tasks
        available = [a for a in actions if a.id not in self._skipped_ids]

        if not available:
            return None

        if window < QUICK_WIN_THRESHOLD:
            # Quick Wins: short tasks or @admin
            candidates = [
                a
                for a in available
                if (a.estimated_duration is not None and a.estimated_duration <= 15)
                or "@admin" in a.context_tags
            ]
            if candidates:
                return candidates[0]

        elif window > DEEP_WORK_THRESHOLD:
            # Deep Work: high-energy, high-priority tasks
            candidates = [
                a
                for a in available
                if a.meta_payload.get("energy") == "high"
                or a.meta_payload.get("priority") == 1
            ]
            if candidates:
                return candidates[0]

        # Fallback: first available task
        return available[0] if available else None

    def skip_task(self, item_id: str) -> None:
        """Mark a task as skipped for this session.

        Skipped tasks won't be selected again until the session ends
        or reset_skipped() is called.

        Args:
            item_id: ID of the task to skip.
        """
        self._skipped_ids.add(item_id)

    def reset_skipped(self) -> None:
        """Clear all skipped tasks, making them eligible for selection again."""
        self._skipped_ids.clear()

    def complete_task(self, item_id: str) -> None:
        """Mark a task as completed.

        Args:
            item_id: ID of the task to complete.
        """
        self._engine.complete_item(item_id)

    def get_resources_for_task(self, item: Item) -> list[Resource]:
        """Get resources matching the task's tags.

        Args:
            item: The task (Item) whose context_tags are used for matching.

        Returns:
            List of Resource objects with matching tags, or [] if no tags.
        """
        if not item.context_tags:
            return []
        return self._engine.get_resources_by_tags(item.context_tags)

    def get_semantic_resources_for_task(self, item: Item, top_k: int = 3) -> list[VectorHit]:
        """Get semantically related resources for task title."""
        return self._engine.get_semantic_resources(item.title, top_k=top_k)

    def get_task_count(self) -> int:
        """Get total count of available active tasks.

        Returns:
            Number of active tasks (excluding skipped).
        """
        actions = self._engine.next_actions()
        return len([a for a in actions if a.id not in self._skipped_ids])

    def get_window_description(self) -> str:
        """Get human-readable description of current time window.

        Returns:
            Description like "You have 45 mins before 'Weekly Sync'"
            or "Open schedule - no upcoming events".
        """
        window, event_title = self.get_time_window()

        if event_title is None:
            return "Open schedule - no upcoming events"

        if window < 60:
            return f"You have {window} mins before '{event_title}'"
        else:
            hours = window // 60
            mins = window % 60
            if mins > 0:
                return f"You have {hours}h {mins}m before '{event_title}'"
            else:
                return f"You have {hours}h before '{event_title}'"

    def get_mode_indicator(self) -> str:
        """Get indicator for current focus mode type.

        Returns:
            Mode description based on time window.
        """
        window, _ = self.get_time_window()

        if window < QUICK_WIN_THRESHOLD:
            return "Quick Wins Mode"
        elif window > DEEP_WORK_THRESHOLD:
            return "Deep Work Mode"
        else:
            return "Standard Mode"
