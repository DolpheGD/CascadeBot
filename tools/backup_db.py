"""
Take a database backup, and prune old ones.

    python -m tools.backup_db                 # take one now
    python -m tools.backup_db --list          # show what exists
    python -m tools.backup_db --keep 30       # override retention

WHY THIS EXISTS. Before it, a backup happened in exactly one situation:
`migrate_db` taking one before a schema change. Between schema changes --
which can be months -- there was no backup at all, and nothing ever
pruned the ones there were. One SQLite file holds every player's
progress: every character, every item, every level, the lot.

The failure mode is not subtle. It is "the file is gone, or corrupt, and
the most recent copy is from whenever the schema last changed."

IT USES SQLITE'S ONLINE BACKUP API, NOT A FILE COPY.

This matters more than it looks, because the bot runs in WAL mode (see
bot/database/db.py). Under WAL, the .db file on disk is NOT a complete
database -- recent commits live in the -wal sidecar until a checkpoint
folds them in. Copying just the .db file while the bot is running
produces a backup that is silently missing the most recent writes, and it
opens cleanly, so nothing tells you.

sqlite3's `Connection.backup()` reads through the WAL and produces a
consistent snapshot of the whole database, while the bot keeps running.
It is also safe to interrupt: it writes to a temporary file and renames
it into place only on success, so a crash mid-backup cannot leave a
truncated file that looks like a real backup.

RETENTION IS A COMPROMISE, deliberately. Keeping every nightly copy of a
growing database fills a disk eventually, and a disk that fills is itself
an outage. Keeping too few means a corruption you notice a week late has
already rotated out of history. The default keeps the most recent
KEEP_DAILY, which is enough to notice and recover from a problem
introduced in the last fortnight.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

# How many backups to keep. Two weeks of nightlies: long enough that a
# corruption noticed late is still recoverable, short enough to bound
# disk use at ~14x the database size.
KEEP_DAILY = 14

BACKUP_SUFFIX = ".autobackup-"


def database_path(database_url: str) -> Path | None:
    """The SQLite file behind `database_url`, or None if it isn't SQLite.

    A Postgres or MySQL deployment needs its own backup story (pg_dump on
    a cron, a managed snapshot) and this tool has nothing useful to say
    about one. Returning None rather than guessing is the honest answer.
    """
    if not database_url.startswith("sqlite"):
        return None
    _, _, tail = database_url.partition("///")
    return Path(tail) if tail else None


def backup_dir(path: Path) -> Path:
    """Backups live beside the database, in their own directory.

    Beside it rather than in a system location so a deployment that moves
    the database moves its history with it, and in a subdirectory so a
    fortnight of copies does not bury the working file.
    """
    return path.parent / "backups"


def take_backup(path: Path, destination: Path | None = None) -> Path:
    """Snapshot `path` via SQLite's online backup API.

    Written to a `.partial` file and renamed on success, so an
    interrupted run leaves no file rather than a plausible-looking
    truncated one.
    """
    directory = backup_dir(path)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = destination or directory / f"{path.stem}{BACKUP_SUFFIX}{stamp}{path.suffix}"
    partial = destination.with_suffix(destination.suffix + ".partial")

    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(partial)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    partial.replace(destination)
    return destination


def existing_backups(path: Path) -> list[Path]:
    directory = backup_dir(path)
    if not directory.is_dir():
        return []
    found = [p for p in directory.iterdir()
             if p.name.startswith(f"{path.stem}{BACKUP_SUFFIX}") and not p.name.endswith(".partial")]
    return sorted(found, key=lambda p: p.name)


def prune(path: Path, keep: int = KEEP_DAILY) -> list[Path]:
    """Delete all but the newest `keep` backups. Returns what it removed."""
    backups = existing_backups(path)
    if len(backups) <= keep:
        return []
    doomed = backups[: len(backups) - keep]
    for old in doomed:
        try:
            old.unlink()
        except OSError:
            # A backup that cannot be deleted is not worth failing over;
            # the next run will try again and the disk-space concern is
            # gradual, not immediate.
            pass
    return doomed


def run(database_url: str, keep: int = KEEP_DAILY) -> tuple[Path | None, int]:
    """Take one backup and prune. Returns (backup path, number pruned).

    Returns (None, 0) for a non-SQLite database rather than raising --
    it's called from a scheduled task, and a Postgres deployment should
    log one line about it, not crash a loop every night.
    """
    path = database_path(database_url)
    if path is None or not path.exists():
        return None, 0
    destination = take_backup(path)
    return destination, len(prune(path, keep))


def _human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.1f}{unit}"
        size /= 1024
    return f"{size:,.1f}GB"


def main() -> int:
    sys.path.insert(0, ".")
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", type=int, default=KEEP_DAILY,
                        help=f"how many backups to retain (default {KEEP_DAILY})")
    parser.add_argument("--list", action="store_true",
                        help="show existing backups and exit")
    args = parser.parse_args()

    from bot.config import DATABASE_URL

    path = database_path(DATABASE_URL)
    if path is None:
        print(f"{DATABASE_URL.split('://')[0]} is not SQLite -- this tool "
              f"only backs up SQLite files. Use your database's own backup "
              f"tooling (pg_dump, managed snapshots).")
        return 0
    if not path.exists():
        print(f"no database at {path} yet -- nothing to back up")
        return 0

    if args.list:
        backups = existing_backups(path)
        print(f"{len(backups)} backup(s) in {backup_dir(path)}")
        for backup in backups:
            print(f"   {backup.name:<48}{_human(backup.stat().st_size):>10}")
        return 0

    destination, pruned = run(DATABASE_URL, args.keep)
    print(f"backed up {path.name} ({_human(path.stat().st_size)}) "
          f"-> {destination.name}")
    if pruned:
        print(f"pruned {pruned} backup(s) beyond the newest {args.keep}")
    print(f"{len(existing_backups(path))} backup(s) retained in {backup_dir(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
