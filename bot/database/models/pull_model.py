"""
Pull history -- the last N results on each banner.

Exists because a gacha without a history is a gacha players do not
trust. "Did I actually get that 5-star or did I misread it", "how many
pulls since my last one", "what did the ten-pull give me" are all
questions the game could not answer, and the only alternative was asking
the player to remember.

Deliberately CAPPED rather than kept forever (see
pull_service.HISTORY_LIMIT). An unbounded log grows without limit for a
feature whose entire use is "what happened recently", and the row a
player wants is never the four-thousandth one.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models.base_model import Base


class PullRecord(Base):
    __tablename__ = "pull_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)

    # "character" or "card". A string rather than an enum because the
    # banner list is content, not schema -- a third banner should be a
    # config change, not a migration.
    banner: Mapped[str] = mapped_column(String(16), index=True)

    name: Mapped[str] = mapped_column(String(64))
    star_rating: Mapped[int] = mapped_column(Integer, default=3)

    # Whether a pity guarantee produced this result. Shown in the
    # history because "was that pity or luck" is the single most common
    # thing a player wants to know about a 5-star.
    was_pity: Mapped[bool] = mapped_column(Integer, default=0)

    pulled_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
