from bot.database.db import engine
from bot.database.models.base_model import Base

# Import every model module so each table registers on Base.metadata before
# create_all runs.
from bot.database.models import (  # noqa: F401
    base_building_model,
    character_model,
    economy_model,
    equipment_model,
    expedition_model,
    gift_model,
    hq_model,
    player_model,
    presence_model,
    quest_model,
    story_model,
    raid_model,
)


# create_all only creates tables that don't exist yet -- it never adds a
# newly-defined column to a table that was already created by an earlier
# version of a model (no Alembic in this project). Any column added to an
# existing model after its table may already be live in deployed DBs needs
# a defensive ALTER TABLE like this one, run once at every startup; it's a
# no-op once the column is actually there.
def _ensure_columns(conn):
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    def add_column(table: str, column: str, ddl_type: str) -> None:
        if table not in tables:
            return  # create_all will build it fresh, with the column already on it
        if column in {col["name"] for col in inspector.get_columns(table)}:
            return
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))

    # custom_name -- lets a player rename their avatar (was hardcoded to
    # the "You" template name everywhere) via
    # character_service.rename_avatar / the /rename command.
    add_column("player_characters", "custom_name", "VARCHAR(32)")

    # Top.gg vote tracking -- see bot/services/vote_service.py. Defaults
    # are spelled out in the DDL as well as on the model so existing rows
    # come back as 0/NULL rather than NULL-where-an-int-is-expected.
    add_column("players", "last_vote_claimed_at", "DATETIME")
    add_column("players", "vote_streak", "INTEGER DEFAULT 0")
    add_column("players", "total_votes", "INTEGER DEFAULT 0")

    # Character gacha pity counters -- see
    # bot/game/economy/character_gacha_config.py. Existing players start
    # at 0, i.e. a fresh pity cycle, which is the generous read of an
    # ambiguous situation (we have no pull history to reconstruct from).
    add_column("players", "pity_since_five_star", "INTEGER DEFAULT 0")
    add_column("players", "pity_since_four_star", "INTEGER DEFAULT 0")

    # Echoes -- the duplicate currency (bot/game/economy/resonance_config.py).
    # Existing players start at 0 rather than being paid retroactively for
    # duplicates they already pulled; their RESONANCE, though, is derived
    # from dupe_count and so applies immediately with no backfill at all
    # (see resonance_config.resonance_for).
    add_column("players", "echoes", "INTEGER DEFAULT 0")

    # Hardest raid difficulty a participant fought at -- drives the
    # absolute reward bonus. NULL on existing rows reads as the default
    # difficulty, i.e. a 1.0x bonus, so nobody's in-flight raid changes.
    add_column("raid_participants", "best_difficulty", "VARCHAR(16)")


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _ensure_columns(conn)


if __name__ == "__main__":
    init_db()
