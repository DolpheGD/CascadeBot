"""
The database engine, and the SQLite settings that keep it usable under a
Discord bot's concurrency.

----------------------------------------------------------------------
WHY THIS FILE HAS PRAGMAS IN IT NOW
----------------------------------------------------------------------
Reported from a live session: a move in an expedition died with

    sqlite3.OperationalError: disk I/O error

on db.commit(), and every interaction for the next minute failed with
"interaction expired" behind it.

SQLite's defaults are built for a single process doing one thing at a
time. This bot is one process doing many things at once -- every player
in every server shares one engine -- and the defaults have three sharp
edges that show up exactly under that load:

  1. THE ROLLBACK JOURNAL TAKES A DATABASE-WIDE WRITE LOCK. While an
     expedition commits, every other command in the bot -- reads
     included -- blocks on the event loop waiting for it. That is the
     contention bot/utils/responses.py's docstring describes as the
     cause of four separate crashes in one evening, and it was treated
     there as something to survive rather than something to remove.
     WAL removes it: readers never block writers and writers never block
     readers.

  2. THERE IS NO BUSY TIMEOUT. On lock contention SQLite gives up
     INSTANTLY rather than waiting, surfacing as "database is locked" or
     an I/O error on a database that is completely healthy. Five seconds
     of patience turns almost all of those into a slight delay nobody
     notices.

  3. FULL SYNC ON EVERY COMMIT. Correct for a bank, needless for a game
     that is already taking a backup before every migration; NORMAL is
     the standard pairing with WAL and is dramatically cheaper.

None of this makes a genuinely broken disk work -- if the file has been
swapped underneath a running process, or the volume is full, the error
is real and the right thing is to fail loudly. What it does is stop the
bot manufacturing those errors out of ordinary contention.
"""

from sqlalchemy import create_engine, event

from bot.config import DATABASE_URL

# Seconds SQLite will wait for a lock before giving up. See point 2.
BUSY_TIMEOUT_SECONDS = 5

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # check_same_thread is off because discord.py hands work to a thread
    # pool; the sessions themselves are still used one-at-a-time.
    connect_args={"check_same_thread": False, "timeout": BUSY_TIMEOUT_SECONDS},
)


@event.listens_for(engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, _record):
    """Set on every new connection, not once at startup.

    A pooled engine opens connections lazily and can replace them, and
    PRAGMA journal_mode is per-connection for everything except WAL
    (which is persistent in the file). Applying them on connect means a
    connection made an hour after startup is configured identically to
    the first one -- the alternative is a subtly different set of
    guarantees depending on which pooled connection served the request.
    """
    # Only meaningful for SQLite; harmless to guard in case the URL ever
    # points somewhere else.
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_SECONDS * 1000}")
        # Enforce the foreign keys the schema declares. Off by default in
        # SQLite, which means the constraints in the models were
        # documentation rather than rules.
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
