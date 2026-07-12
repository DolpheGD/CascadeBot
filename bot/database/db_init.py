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
)


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
