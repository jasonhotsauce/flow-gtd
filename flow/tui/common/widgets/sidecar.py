"""Sidecar panel: RAG context (filename, score, snippet)."""

from textual.widgets import Static


class RAGContextPanel(Static):
    """Displays top RAG results (filename, score, snippet) for the selected task.

    Provides contextual information from the knowledge base to help users
    with the current task.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_loading = False

    def show_results(self, results: list[dict]) -> None:
        """Update content with list of {filename, score, snippet}.

        Args:
            results: List of RAG results with filename, score, and snippet.
        """
        self._is_loading = False

        if not results:
            self.update(
                "📭 No Related Documents\n"
                "────────────────────────────\n\n"
                "No matching context found.\n\n"
                "💡 Tip: Capture URLs or PDFs to\n"
                "   build your knowledge base."
            )
            return

        lines = ["🔗 Related Context", "────────────────────────────", ""]

        for i, r in enumerate(results, 1):
            fn = r.get("filename", "document")
            score = r.get("score")
            snippet = (r.get("snippet") or "")[:180]
            if len((r.get("snippet") or "")) > 180:
                snippet += "..."

            # Format score as percentage if available
            score_str = f" ({score:.0%})" if score is not None else ""

            # Build result card
            lines.append(f"📄 {fn}{score_str}")
            lines.append("┄" * 28)
            lines.append(snippet)
            lines.append("")

        self.update("\n".join(lines))

    def show_loading(self) -> None:
        """Show loading state."""
        self._is_loading = True
        self.update(
            "🔗 Related Context\n"
            "────────────────────────────\n\n"
            "⏳ Searching knowledge base..."
        )

    def show_error(self, message: str = "Failed to load") -> None:
        """Show error state.

        Args:
            message: Error message to display.
        """
        self._is_loading = False
        self.update(
            "🔗 Related Context\n"
            "────────────────────────────\n\n"
            f"⚠️ {message}\n\n"
            "Please try again."
        )

    def clear_results(self) -> None:
        """Clear and show default state."""
        self._is_loading = False
        self.update(
            "🔗 Related Context\n"
            "────────────────────────────\n\n"
            "👆 Select a task to see\n"
            "   related documents.\n\n"
            "────────────────────────────\n"
            "📚 Knowledge base helps you\n"
            "   find relevant context for\n"
            "   your current work."
        )
