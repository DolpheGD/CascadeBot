"""
Rebuild a usable database out of a corrupt one.

    python -m tools.recover_db                      # dry run, reports only
    python -m tools.recover_db --write              # writes Cascadebot.recovered.db
    python -m tools.recover_db --write --out X.db   # ...somewhere else

WHAT WENT WRONG, so the next person recognises it
-------------------------------------------------
SQLite reported "database disk image is malformed". The specific failure
was a TRUNCATED FILE: the header said 596 pages, the file was 596 pages,
and b-tree cells pointed at pages 597-644 that no longer existed. About
200 KB off the end of the file was gone.

That is what you get from a database that was copied, zipped or synced
WHILE the bot had a write transaction open, or from a rollback journal
(`Cascadebot.db-journal`) being applied to a file that had already moved
on. It is not a schema problem and no migration caused it -- the
migration was simply the first thing to read every row and therefore the
first thing to notice.

WHY NOT JUST RESTORE THE BACKUP
-------------------------------
Because almost nothing was actually lost. Corruption on a truncated file
is local to the pages that went missing: here, 24 of 26 tables read
perfectly and only `inventory_items` and `expeditions` were damaged.
Restoring the newest clean backup would have thrown away every table
that was fine -- a player, 13 characters, 112 items and two quests --
to fix two tables that were mostly fine too.

THE APPROACH
------------
1. Copy the newest CLEAN backup. That gives a structurally sound file
   with a correct schema, which is the one thing the corrupt database
   can no longer be trusted to provide.
2. For every table, read the live database ROW BY ROW and overwrite the
   backup's contents with whatever the live file can still produce. A
   row that raises DatabaseError is skipped rather than aborting the
   table -- that is the whole trick, and it's why this recovers 1,106 of
   ~1,164 items instead of zero.
3. Rows that exist in the backup but can no longer be read from the live
   file are LEFT IN PLACE, so they come back at their backup-time state
   instead of vanishing. That is a deliberate trade: slightly stale data
   beats missing data, and it is flagged in the report either way.

The original file is opened read-only and is never modified. The output
is a new file, so nothing is committed until you look at the report and
move it into place yourself.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sqlite3
import sys

DEFAULT_LIVE = "Cascadebot.db"
DEFAULT_OUT = "Cascadebot.recovered.db"
BACKUP_GLOB = "Backupdata/Cascadebot.backup-*.db"

# How far past the last known id to keep probing when a table's own
# max(rowid) can't be read (the query walks the b-tree and hits the
# corruption). Cheap enough to be generous.
PROBE_MARGIN = 500


def integrity(path: str) -> str:
    """'ok', or the first line of what's wrong. Never raises."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute("PRAGMA integrity_check").fetchone()[0].splitlines()[0]
        finally:
            con.close()
    except Exception as exc:  # a file too broken to even open
        return f"{type(exc).__name__}: {exc}"


def newest_clean_backup(pattern: str = BACKUP_GLOB) -> str | None:
    """Newest backup that passes integrity_check. Checked rather than
    assumed -- 'newest' and 'good' are not the same property, and the
    whole point of this script is that a file can look fine and not be."""
    for path in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True):
        if integrity(path) == "ok":
            return path
    return None


def table_names(con: sqlite3.Connection) -> list[str]:
    return [row[0] for row in con.execute(
        "select name from sqlite_master where type='table' "
        "and name not like 'sqlite_%' order by name"
    )]


def read_rows(con: sqlite3.Connection, table: str, upper_hint: int) -> tuple[list[tuple], bool]:
    """Returns (rows, intact), where each row is (rowid, *columns) and
    `intact` means the table read cleanly from end to end.

    `intact` decides whether the backup is allowed to contribute to this
    table at all, and getting that wrong is worse than the corruption.
    If a table reads completely, its contents are AUTHORITATIVE: a row
    the backup has and the live file doesn't was deleted on purpose --
    a completed quest, a sold item, a reset account. Backfilling those
    doesn't recover data, it resurrects records the game already retired,
    and an early version of this quietly brought back 14 finished quests
    and a deleted player. Only tables that actually failed to read get
    topped up from the backup.

    Tries the fast path first (one scan). If the scan hits a bad page it
    restarts row by row, because a single unreadable page must not cost
    us the rows on either side of it -- which is exactly what the plain
    `SELECT *` in the migration did.

    The fast path is BUFFERED rather than streamed. A scan that dies
    halfway has already handed back the rows it read, and yielding them
    before falling back to the row-by-row pass means every one of those
    rows gets collected twice -- which is how an early version of this
    reported 2,199 recovered items out of a possible 1,164.

    Rows are keyed by ROWID, not by the first column. Most tables here
    have an integer `id` that happens to equal the rowid, but not all
    do, and keying on the wrong one silently reports every recovered row
    as missing.
    """
    try:
        return con.execute(f'select rowid, * from "{table}"').fetchall(), True
    except sqlite3.DatabaseError:
        pass

    rows = []
    for rowid in range(1, upper_hint + 1):
        try:
            row = con.execute(
                f'select rowid, * from "{table}" where rowid=?', (rowid,)
            ).fetchone()
        except sqlite3.DatabaseError:
            continue
        if row is not None:
            rows.append(row)
    return rows, False


def upper_bound(live: sqlite3.Connection, backup: sqlite3.Connection, table: str) -> int:
    """Highest rowid worth probing for. Prefers the live file's own
    max(rowid); falls back to the backup's plus a margin, since the live
    database has only ever grown relative to it."""
    for con in (live, backup):
        try:
            value = con.execute(f'select max(rowid) from "{table}"').fetchone()[0]
            if value:
                return int(value) + PROBE_MARGIN
        except sqlite3.DatabaseError:
            continue
    return PROBE_MARGIN


def recover(live_path: str, backup_path: str, out_path: str, write: bool) -> int:
    print("CascadeBot database recovery" + ("" if write else "   [DRY RUN -- nothing will be written]"))
    print(f"   corrupt : {live_path}   ({integrity(live_path)})")
    print(f"   backup  : {backup_path}   (ok)")
    print(f"   output  : {out_path}\n")

    if write:
        if os.path.exists(out_path):
            print(f"refusing to overwrite an existing {out_path} -- move it aside first")
            return 1
        shutil.copy2(backup_path, out_path)

    live = sqlite3.connect(f"file:{live_path}?mode=ro", uri=True)
    backup = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    out = sqlite3.connect(out_path) if write else None
    if out is not None:
        out.execute("PRAGMA foreign_keys=OFF")
        # The output is a scratch file that gets an integrity_check before
        # anyone is told to use it, so durability during the build buys
        # nothing and costs a lot: the default rollback journal writes a
        # second copy of every page it touches, which on a synced or
        # network-backed folder is slow enough that an interrupted run
        # leaves a 2 MB hot journal and an unopenable output. Building in
        # memory and flushing once removes that failure mode entirely.
        out.execute("PRAGMA journal_mode=MEMORY")
        out.execute("PRAGMA synchronous=OFF")

    print(f"{'table':<26}{'recovered':>11}{'from backup':>13}{'status':>10}")
    print("-" * 60)

    stale_total = 0
    for table in table_names(backup):
        backup_ids = {row[0] for row in backup.execute(f'select rowid from "{table}"')}
        rows, intact = read_rows(live, table, upper_bound(live, backup, table))
        recovered_ids = {row[0] for row in rows}

        if rows and out is not None:
            columns = [d[0] for d in live.execute(
                f'select * from "{table}" limit 0').description]
            placeholders = ", ".join("?" * (len(columns) + 1))
            quoted = ", ".join(f'"{c}"' for c in columns)
            out.execute(f'delete from "{table}"')
            out.executemany(
                f'insert into "{table}" (rowid, {quoted}) values ({placeholders})', rows)

        kept_from_backup = set() if intact else (backup_ids - recovered_ids)
        if kept_from_backup and out is not None:
            # Re-insert only the rows the live file could not produce.
            columns = [d[0] for d in backup.execute(
                f'select * from "{table}" limit 0').description]
            placeholders = ", ".join("?" * (len(columns) + 1))
            quoted = ", ".join(f'"{c}"' for c in columns)
            marks = ", ".join("?" * len(kept_from_backup))
            missing = backup.execute(
                f'select rowid, * from "{table}" where rowid in ({marks})',
                tuple(kept_from_backup)).fetchall()
            out.executemany(
                f'insert or ignore into "{table}" (rowid, {quoted}) values ({placeholders})',
                missing)

        stale_total += len(kept_from_backup)
        status = "ok" if intact else "DAMAGED"
        print(f"{table:<26}{len(rows):>11}{len(kept_from_backup):>13}{status:>10}")

    if out is not None:
        # ---- repair the seam between the two sources -----------------
        #
        # A row restored from the backup can point at a row that the live
        # file legitimately moved on from. Here: three items that were
        # equipped to characters 54 and 55 at backup time, on a player
        # who has since parted with both. The items themselves are real
        # and the player should keep them; it's only the equipped-to
        # link that is stale.
        #
        # Unequipping is the conservative repair -- the loot lands back
        # in their inventory, where they can re-equip it -- and it is
        # strictly better than the alternatives, which are deleting an
        # item somebody owns or shipping a database whose foreign keys
        # don't resolve.
        orphaned = out.execute("""
            update inventory_items
               set character_id = null, is_equipped = 0
             where character_id is not null
               and character_id not in (select id from player_characters)
        """).rowcount
        out.commit()
        if orphaned:
            print(f"\nunequipped {orphaned} restored item(s) whose character no longer exists "
                  f"(kept in the owner's inventory)")

        result = integrity(out_path)
        print(f"\nintegrity_check on the rebuilt file: {result}")
        out.close()
        if result != "ok":
            print("the rebuilt file is NOT clean -- do not put it into service")
            return 1
    live.close()
    backup.close()

    print(f"\n{stale_total} row(s) could not be read from the live file and were kept "
          f"at their backup state.")
    if not write:
        print("\nthis was a dry run -- re-run with --write to produce the file")
    else:
        print(f"\nwrote {out_path}. Stop the bot, move {live_path} aside, rename this "
              f"file into its place, then re-run the migration.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", default=DEFAULT_LIVE, help="the corrupt database")
    parser.add_argument("--backup", default=None,
                        help="clean backup to rebuild onto (default: newest that passes integrity_check)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="where to write the rebuilt database")
    parser.add_argument("--write", action="store_true",
                        help="actually write the output file (default is a dry run)")
    args = parser.parse_args()

    if not os.path.exists(args.live):
        print(f"no such database: {args.live}", file=sys.stderr)
        return 2

    backup = args.backup or newest_clean_backup()
    if backup is None:
        print("no clean backup found to rebuild onto", file=sys.stderr)
        return 2

    return recover(args.live, backup, args.out, args.write)


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
