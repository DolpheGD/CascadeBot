"""Shared logging setup so every module logs consistently."""

from __future__ import annotations

import logging
import sys

from bot.config import DEBUG

_CONFIGURED = False


def setup_logging() -> None:
    """Configure the root 'cascadebot' logger. Safe to call more than once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = logging.DEBUG if DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger("cascadebot")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"cascadebot.{name}")
