"""Shared logging setup so every module logs consistently.

ERRORS GO TO A FILE AS WELL AS THE CONSOLE, and that is the point of most
of this module.

The console is not a record. It scrolls, it is lost on restart, and on a
hosted bot nobody is watching it at 3am -- which is exactly when the
interesting failures happen. Two live crashes in this project were only
found because somebody happened to catch them in a terminal buffer, and
by then the tracebacks above them were already gone.

So every WARNING and above is also appended to `logs/errors.log`, with
the full traceback, and rotated rather than truncated so history
survives. `logs/cascadebot.log` gets everything at the configured level,
for when the question is "what led up to it" rather than "what broke".

WHY discord.py's OWN LOGGER IS CAPTURED TOO. The crashes worth reading
are usually raised inside discord.py's command tree, not inside this
package -- `CommandInvokeError: Command 'adventure' raised an exception`
is logged by `discord.app_commands`, and a handler attached only to
`cascadebot` would never see it. Both trees are attached, so the file is
the whole picture rather than our half of it.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from bot.config import DEBUG

_CONFIGURED = False

# Beside the code, not in a system location, so a deployment that moves
# the bot moves its logs with it -- the same reasoning as backup_db's
# `backups/` directory.
LOG_DIR = Path(os.getenv("CASCADEBOT_LOG_DIR") or "logs")

# Rotation, not truncation. 5 MB x 10 keeps roughly the last few weeks of
# a busy bot's errors, which is the window in which somebody actually
# asks "what happened on Tuesday". Truncating on restart would throw away
# the log at precisely the moment a crash-loop is generating it.
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 10

# Loggers whose records are worth keeping. "cascadebot" is ours;
# "discord" carries the command-tree tracebacks, which is where an
# unhandled command error actually surfaces.
CAPTURED = ("cascadebot", "discord")


def _file_handler(filename: str, level: int) -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / filename, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(
        # Module and line number included deliberately: the first thing
        # anybody wants from an error log is where to look.
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    return handler


def setup_logging() -> None:
    """Configure logging. Safe to call more than once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = logging.DEBUG if DEBUG else logging.INFO

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    handlers: list[logging.Handler] = [console]
    try:
        handlers.append(_file_handler("errors.log", logging.WARNING))
        handlers.append(_file_handler("cascadebot.log", level))
    except OSError as exc:
        # A read-only or full disk must not stop the bot from running.
        # Logging that we cannot log is the one message that has to go to
        # the console, since the file is exactly what is unavailable.
        print(f"WARNING: could not open log files ({exc}); console only",
              file=sys.stderr)

    root = logging.getLogger("cascadebot")
    root.setLevel(level)
    for handler in handlers:
        root.addHandler(handler)
    root.propagate = False

    # discord.py's own loggers: FILE ONLY, no second console handler.
    # discord.py already prints to the console via its own setup, and
    # attaching ours as well would double every line it emits.
    discord_log = logging.getLogger("discord")
    discord_log.setLevel(logging.INFO)
    for handler in handlers[1:]:
        discord_log.addHandler(handler)

    # UNCAUGHT EXCEPTIONS, which by definition never reach a log call.
    # Without this the one traceback that killed the process is the one
    # that is not in the file.
    def _log_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("cascadebot.crash").critical(
            "UNCAUGHT EXCEPTION -- the process is going down",
            exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _log_uncaught

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"cascadebot.{name}")


def error_log_path() -> Path:
    """Where the errors are, for anything that wants to tell the owner."""
    return LOG_DIR / "errors.log"
