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

    # SET ONCE BY THE MIGRATION, for players who existed before story
    # mode gated anything.
    #
    # prologue_complete alone was not enough: it only covers features the
    # PROLOGUE unlocks, and Chapter 1-2 gate six more (forge, lab, raids,
    # gifting, exchange, abyss). A player who had only ever run /start
    # passed the prologue check and still failed the "looks like a
    # veteran" heuristic -- one character, no expeditions -- so they lost
    # six features they previously had. Recording the fact directly means
    # it can never be re-derived wrongly.
    grandfathered: Mapped[bool] = mapped_column(Boolean, default=False)

    # ------------------------------------------------------------------
    # Overworld position (bot/game/story/map_config.py).
    #
    # NULL area means "hasn't stepped onto the map yet", which is how an
    # existing player who predates the overworld reads -- map_service
    # spawns them rather than treating (0, 0) as a real position, since
    # (0, 0) is a wall in every authored area.
    # ------------------------------------------------------------------
    area: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pos_x: Mapped[int] = mapped_column(Integer, default=0)
    pos_y: Mapped[int] = mapped_column(Integer, default=0)

    # {area_id: [[x, y], ...]} -- tiles the player has stood on. Purely
    # informational (the grid is never hidden), but it's what lets an
    # area tell you how much of it you've actually seen.
    visited: Mapped[dict] = mapped_column(JSON, default=dict)

    # An optional HUNT the player has accepted: {"area", "char", "level",
    # "enemies": [...], "grant": {...}}. Separate from `combat_state`'s
    # mission battles because a hunt is not part of any mission -- losing
    # one costs nothing and must not touch mission progress.
    pending_hunt: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # {area_id: [tile_char, ...]} -- one-shot tiles already consumed, so
    # a note that has been read stops advertising itself.
    read_tiles: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<PlayerStory {self.player_id} active={self.active_mission!r} "
                f"beat={self.beat_index} cleared={len(self.completed_missions or [])}>")
