"""Sidecar panel: Tag-based resource display."""

from typing import Optional

from textual.widgets import Static

from flow.models import Resource


class ResourceContextPanel(Static):
    """Displays resources matching the selected task's tags.

    Provides instant contextual information based on tag matching
    between tasks and saved resources.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_tags: list[str] = []

    def show_resources(
        self,
        resources: list[Resource],
        task_tags: Optional[list[str]] = None,
    ) -> None:
        """Update content with matching resources.

        Args:
            resources: List of Resource objects to display.
            task_tags: Tags from the current task (for display).
        """
        self._current_tags = task_tags or []

        if not resources:
            tags_line = ""
            if self._current_tags:
                tags_line = f"\nTask tags: {', '.join(self._current_tags)}\n"
            self.update(
                "📭 No Related Resources\n"
                "────────────────────────────\n"
                f"{tags_line}\n"
                "No matching resources found.\n\n"
                "💡 Tip: Use 'flow save <url>'\n"
                "   to add resources."
            )
            return

        lines = ["🔗 Related Resources", "────────────────────────────"]

        # Show task tags if available
        if self._current_tags:
            lines.append(f"Tags: {', '.join(self._current_tags)}")
        lines.append("")

        for r in resources[:5]:  # Limit to 5 resources
            # Icon based on content type
            icon = {"url": "🔗", "file": "📄", "text": "📝"}.get(r.content_type, "📎")

            # Title or source
            title = r.title or r.source[:40]
            if len(title) > 35:
                title = title[:32] + "..."

            lines.append(f"{icon} {title}")

            # Show resource tags
            if r.tags:
                tags_display = ", ".join(r.tags[:4])
                if len(r.tags) > 4:
                    tags_display += f" +{len(r.tags) - 4}"
                lines.append(f"   [{tags_display}]")

            # Summary/preview
            if r.summary:
                summary = r.summary[:100]
                if len(r.summary) > 100:
                    summary += "..."
                lines.append(f"   {summary}")

            lines.append("")

        # Footer with count
        if len(resources) > 5:
            lines.append(f"   ... and {len(resources) - 5} more")

        self.update("\n".join(lines))

    def show_error(self, message: str = "Failed to load") -> None:
        """Show error state.

        Args:
            message: Error message to display.
        """
        self.update(
            "🔗 Related Resources\n"
            "────────────────────────────\n\n"
            f"⚠️ {message}\n\n"
            "Please try again."
        )

    def clear_resources(self) -> None:
        """Clear and show default state."""
        self._current_tags = []
        self.update(
            "🔗 Related Resources\n"
            "────────────────────────────\n\n"
            "👆 Select a task to see\n"
            "   related resources.\n\n"
            "────────────────────────────\n"
            "📚 Resources are matched to\n"
            "   tasks via shared tags."
        )


# Alias for backward compatibility
RAGContextPanel = ResourceContextPanel
