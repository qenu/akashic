from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


class AppLogger:
    """Central Loguru setup for console + rotating file logs."""

    _configured = False

    @classmethod
    def configure(cls, base_dir: str | Path | None = None, level: str = "INFO") -> None:
        if cls._configured:
            return

        root = Path(base_dir) if base_dir is not None else Path.cwd()
        log_dir = root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.remove()
        logger.add(
            sys.stderr,
            level=level,
            colorize=False,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[component]} | {message}",
        )
        logger.add(
            log_dir / "app.log",
            level=level,
            rotation="5 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[component]} | {message}",
        )

        cls._configured = True
        logger.bind(component="logger").info("Logging initialized at {}", log_dir)

    @staticmethod
    def get_logger(component: str = "app"):
        return logger.bind(component=component)
