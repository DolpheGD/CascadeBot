from bot.database.db import engine
from bot.database.models.base_model import Base

# Import every model module so each table registers on Base.metadata before
# create_all runs.
from bot.database.models import (  # noqa: F401
    character_model,
    economy_model,
    equipment_model,
    expedition_model,
    hq_model,
    player_model,
    quest_model,
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
    if "player_characters" in inspector.get_table_names():
        existing_columns = {col["name"] for col in inspector.get_columns("player_characters")}
        if "custom_name" not in existing_columns:
            # custom_name -- lets a player rename their avatar (was
            # hardcoded to the "You" template name everywhere) via
            # character_service.rename_avatar / the /rename command.
            conn.execute(text("ALTER TABLE player_characters ADD COLUMN custom_name VARCHAR(32)"))


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _ensure_columns(conn)


if __name__ == "__main__":
    init_db()
