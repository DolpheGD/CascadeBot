"""
Earned achievements.

WHY THIS TABLE EXISTS AT ALL, given achievements are DERIVED.

Whether a player has earned something is computed fresh from their state
(see achievement_service.metrics), so in principle nothing needs storing.
Two things do need it:

  1. WHEN. "Earned 3 weeks ago" is most of what makes a list of
     achievements feel like a record rather than a checklist, and the
     moment of earning is not recoverable after the fact.

  2. WHETHER IT IS NEW. Telling a player they just earned something
     requires knowing what they had last time anybody looked. Without a
     row, every screen would either announce everything or announce
     nothing.

A row is therefore a RECEIPT, not the source of truth. If this table were
wiped, every achievement would still be correctly earned on the next
sync -- only the dates and the "new!" markers would be lost. That is the
right failure mode for a cosmetic system.

NOTHING IS EVER REVOKED. A player who earns "Own every character" and
then prestiges keeps it. Taking an achievement away for progressing is a
bizarre message, and the sync deliberately only ever inserts.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class PlayerAchievement(Base):
    __tablename__ = "player_achievements"
    __table_args__ = (
        UniqueConstraint("player_id", "achievement_id", name="uq_player_achievement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True)

    # The config id, not a foreign key -- achievements live in code, and
    # a removed one should leave a harmless orphan row rather than break
    # a delete.
    achievement_id: Mapped[str] = mapped_column(String(64), index=True)

    earned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
