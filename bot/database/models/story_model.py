"""
Per-player story progress.

One row per player, holding four things:

  * which missions they've cleared (so a mission can be one-time, and a
    replay can pay less)
  * their FLAGS -- what they chose, read by later beats
  * the mission currently in progress, and how far into it they are
  * that mission's serialized battle, if they're mid-fight

The last two are why this is a table and not a computed value. A story
mission can contain a real battle that takes several minutes of button
presses, and the bot can restart during it. Expeditions already solve
this by serializing combat to a column and running every interaction as
load -> mutate -> save; story missions use the same approach for the same
reason.

PROLOGUE_COMPLETE IS AN EXPLICIT COLUMN, not derived from
completed_missions. Deriving it would mean that adding a prologue mission
later silently re-locks the game for everyone who already finished --
including every player grandfathered in by the migration, who has no
prologue mission ids recorded at all.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class PlayerStory(Base):
    __tablename__ = "player_stories"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )

    # Mission ids already cleared at least once. A list rather than a set
    # because JSON has no set; membership tests go through the service.
    completed_missions: Mapped[list] = mapped_column(JSON, default=list)

    # {flag_name: value}. Absent reads as False -- see story_config's
    # note on flags being additive.
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

    # The mission in progress, if any, and the index of the beat the
    # player is sitting on inside it.
    active_mission: Mapped[str | None] = mapped_column(String(64), nullable=True)
    beat_index: Mapped[int] = mapped_column(Integer, default=0)

    # Serialized Battle for a `battle` beat in progress. Same shape as
    # Expedition.combat_state.
    combat_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    prologue_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<PlayerStory {self.player_id} active={self.active_mission!r} "
                f"beat={self.beat_index} cleared={len(self.completed_missions or [])}>")
