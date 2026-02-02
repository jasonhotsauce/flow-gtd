"""Application Bootstrap (Entry Point)."""

from .cli import app


def main() -> None:
    """Main entry point for the Flow CLI."""
    app()


if __name__ == "__main__":
    main()
