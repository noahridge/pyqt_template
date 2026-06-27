"""Logging setup: console + rotating file.

HMI panels run unattended, so a durable log on disk is the primary forensic
tool when something goes wrong at 3am. We use a size-based rotating handler so
the log can't fill the disk on a long-running kiosk.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-8s %(threadName)-12s %(name)s: %(message)s"

_configured = False


def configure_logging(
    *,
    level: int = logging.INFO,
    log_dir: Path | None = None,
    log_file: str = "hmi.log",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> None:
    """Configure the root logger. Idempotent — safe to call more than once."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _configured = True
    logging.getLogger(__name__).info("Logging configured (level=%s)", logging.getLevelName(level))
