"""
Deleting an account completely, for testing.

Used by /admin_reset. The point is to be able to replay the prologue --
and the first-run experience generally -- without hand-editing the
database or making a second Discord account.

----------------------------------------------------------------------
WHY THE TABLE LIST IS DERIVED, NOT WRITTEN DOWN
----------------------------------------------------------------------
The obvious implementation is a hardcoded list of tables to delete from.
It is also the one that rots: this schema has grown a new player-owned
table almost every time a feature landed (player_abyss, player_forges,
player_labs, player_research, player_stories...), and a reset that
misses one is worse than no reset at all. You get a "fresh" account that
still remembers it finished Chapter 2, and the bug looks like a story
bug, not a reset bug.

So the delete order is computed from SQLAlchemy's metadata every time it
runs: anything with a foreign key to players.id is included
automatically, and a table added next month is covered without anyone
remembering to come back here.

The one thing introspection CAN'T find is a column that holds a player
id without declaring a foreign key -- see SOFT_REFERENCES below, which
is the short, explicit list of those. `tools/check_reset.py` fails if a
new one appears that isn't listed.

----------------------------------------------------------------------
WHY THE PLAYER ROW GOES TOO
----------------------------------------------------------------------
/start refuses to do anything when a Player row already exists ("You've
already begun your journey"), so blanking the row's columns in place
would produce an account that is empty but can never be started again --
exactly the state this command exists to escape. Deleting the row is
what makes /start work.

Nothing is lost by that: Player.id IS the Discord user ID, so running
/start afterwards recreates the account under the same id.
"""

from __future__ import annotations

from sqlalchemy import inspect as sqla_inspect, text

from bot.database.models.base_model import Base
from bot.database.models.player_model import Player

# Columns that hold a player id WITHOUT a foreign key declaring it, so
# metadata introspection can't see them.
#
#   gifts.recipient_id     -- an inbound gift, still uncollected. Left
#                             behind it would be addressed to an account
#                             that no longer exists, and would land in
#                             the new one's inbox after /start.
#   player_guilds.player_id -- presence tracking (which servers this
#                             player has been seen in).
#
# {table name: column name}. Anything found by tools/check_reset.py that
# isn't here is a bug in one of the two places.
SOFT_REFERENCES: dict[str, str] = {
    "gifts": "recipient_id",
    "player_guilds": "player_id",
}

# Tables that reference a player but are DELIBERATELY not cleared,
# because they are not that player's property:
#
#   guild_raids -- a server's shared raid. Deleting it because one
#                  participant reset would end a raid for everybody else
#                  in the server. The raid_participants row IS removed,
#                  which is the part that belongs to this player.
KEEP: frozenset[str] = frozenset({"guild_raids"})


def _player_id_columns(table) -> list[str]:
    """Every column in `table` that holds a player id -- declared foreign
    keys plus the soft references above."""
    columns = [
        column.name for column in table.columns
        if any(fk.target_fullname == "players.id" for fk in column.foreign_keys)
    ]
    soft = SOFT_REFERENCES.get(table.name)
    if soft is not None and soft not in columns and soft in table.columns:
        columns.append(soft)
    return columns


def player_owned_tables() -> list[tuple[str, list[str]]]:
    """[(table name, [columns holding a player id])] for every table this
    reset touches, children first.

    Order matters: a child row pointing at players.id has to go before
    the row it points at, or SQLite rejects the delete when foreign keys
    are enforced. Metadata.sorted_tables is dependency order (parents
    first), so reversing it gives a safe delete order for free -- and
    keeps giving one when tables are added.
    """
    out = []
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in KEEP or table.name == Player.__tablename__:
            continue
        columns = _player_id_columns(table)
        if columns:
            out.append((table.name, columns))
    return out


def _where(columns: list[str]) -> str:
    """WHERE clause matching a player id in any of `columns`.

    Column and table names are interpolated (they come from SQLAlchemy
    metadata, not from anything a user can influence); the ID itself is
    always a bound parameter.
    """
    return " OR ".join(f"{column} = :pid" for column in columns)


def preview(db, player_id: int) -> dict[str, int]:
    """{table: rows that would be deleted}, empty tables omitted.

    Shown to the user BEFORE anything is destroyed. A confirmation
    prompt that says "are you sure?" without saying what will be lost is
    not really a confirmation -- this is what makes the second step of
    /admin_reset a decision rather than a formality.
    """
    counts: dict[str, int] = {}
    connection = db.connection()
    existing = set(sqla_inspect(db.get_bind()).get_table_names())

    for name, columns in player_owned_tables():
        if name not in existing:
            continue  # model exists, migration hasn't run yet
        total = connection.execute(
            text(f"SELECT COUNT(*) FROM {name} WHERE {_where(columns)}"),
            {"pid": int(player_id)},
        ).scalar()
        if total:
            counts[name] = int(total)

    if db.get(Player, player_id) is not None:
        counts[Player.__tablename__] = 1
    return counts


def reset(db, player_id: int) -> dict[str, int]:
    """Delete the account. Returns {table: rows actually deleted}.

    Commits once at the end: a reset that half-succeeded would leave an
    account in a state no code path expects, which is worse than one
    that failed outright and can be retried.
    """
    deleted: dict[str, int] = {}
    connection = db.connection()
    existing = set(sqla_inspect(db.get_bind()).get_table_names())
    pid = int(player_id)

    for name, columns in player_owned_tables():
        if name not in existing:
            continue
        result = connection.execute(
            text(f"DELETE FROM {name} WHERE {_where(columns)}"), {"pid": pid},
        )
        if result.rowcount:
            deleted[name] = int(result.rowcount)

    player = db.get(Player, pid)
    if player is not None:
        db.delete(player)
        deleted[Player.__tablename__] = 1

    db.commit()
    return deleted
