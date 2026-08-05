"""
Void Abyss progress.

One row per player. Everything is JSON keyed by floor number as a STRING,
because JSON object keys are strings and round-tripping them as ints is a
reliable source of "the floor I cleared isn't cleared".
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class PlayerAbyss(Base):
    __tablename__ = "player_abyss"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )

    # {"3": 2} -- best star count ever achieved on that floor. Stars are
    # kept at their BEST, never overwritten downward, so experimenting
    # with a worse team can't cost you a rating you already earned.
    stars: Mapped[dict] = mapped_column(JSON, default=dict)

    # Static floors: {"3": true} once its one-time reward is taken.
    claimed_static: Mapped[dict] = mapped_column(JSON, default=dict)

    # Rotating floors: {"9": 14} -- the rotation index the reward was last
    # claimed in. Claimable again when the current rotation differs, which
    # is what makes the endgame repeatable without being farmable.
    claimed_rotation: Mapped[dict] = mapped_column(JSON, default=dict)

    # ------------------------------------------------------------------
    # An attempt in progress.
    #
    # `run_teams` is [[character_id, ...], ...] -- one list per chamber,
    # locked in BEFORE the first fight. Locking the whole floor's teams up
    # front is the entire point: choosing your second team after seeing
    # what beat your first is a different, much easier game.
    # ------------------------------------------------------------------
    active_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chamber_index: Mapped[int] = mapped_column(Integer, default=0)
    run_teams: Mapped[list | None] = mapped_column(JSON, nullable=True)
    combat_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Star conditions are per-RUN and have to survive a restart mid-floor,
    # so they live here rather than being recomputed from the battle.
    run_flawless: Mapped[int] = mapped_column(Integer, default=1)
    run_fast: Mapped[int] = mapped_column(Integer, default=1)

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<PlayerAbyss {self.player_id} floor={self.active_floor} "
                f"stars={sum((self.stars or {}).values())}>")
