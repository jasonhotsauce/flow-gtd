"""Application Bootstrap (Entry Point)."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .cli import app
from .config import get_settings

# Logging configuration constants
LOG_FILE_MAX_BYTES = 5 * 1024 * 1024  # 5MB max log file size
LOG_FILE_BACKUP_COUNT = 3  # Keep 3 backup log files


def setup_logging() -> None:
    """Configure application-wide logging.

    Logs to both file (data/flow.log) and stderr.
    Log level controlled by FLOW_LOG_LEVEL env var (default: INFO).

    Handles configuration errors gracefully to ensure logging
    is available even if settings fail to load.
    """
    try:
        settings = get_settings()
        log_file = settings.log_file
        log_level = settings.log_level
    except Exception as e:
        # Fallback to defaults if settings fail
        print(f"Warning: Failed to load settings for logging: {e}", file=sys.stderr)
        from pathlib import Path

        log_file = Path("data/flow.log")
        log_level = "INFO"

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter("%(levelname)-8s | %(name)s | %(message)s")

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # File captures everything

    # Console handler (stderr) - only WARNING+ by default to not clutter TUI
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    """Main entry point for the Flow CLI."""
    setup_logging()
    app()


if __name__ == "__main__":
    main()
