"""
Co-op raids -- the game's first genuinely multiplayer system.

Everything else in CascadeBot is single-player: expeditions, domains, HQ
and the gacha all resolve entirely within one Player row. A raid is the
one place where what another person in the same Discord server did
actually changes what you see.

SHAPE OF THE FEATURE. One raid is active per Discord GUILD at a time,
with a large shared HP pool. Any member can attack it, a limited number
of times per raid; each attack runs a normal single battle against the
boss using that player's real squad, and whatever damage they deal is
subtracted from the shared pool and banked to their personal
contribution. When the pool hits zero the raid is DEFEATED and everyone
who contributed can claim a reward scaled to how much they did.

WHY IT'S ASYNCHRONOUS. Discord bot players are not online at the same
time, and a raid that needs four people in the same five minutes is a
raid that never fires. Nobody ever waits on anybody here: you attack
whenever you like, the boss's HP is simply lower than it was last time
if someone else got there first. That also means a raid can't be blocked
by an inactive member, which is the usual failure mode of party content
in an asynchronous medium.

WHY DAMAGE, NOT KILLS. Scoring by damage dealt rather than by who lands
the killing blow means a weaker player's ten attacks still visibly move
the bar, and the reward tiers below reflect participation rather than
luck of timing. It also makes the boss's HP pool the single tuning knob
for "how many people should this take".

THREE TABLES.
  * GuildRaid          -- one row per raid instance (per guild). Holds
                          the shared HP pool and lifecycle state.
  * RaidParticipant    -- one row per (raid, player): damage banked,
                          attacks used, whether the reward is claimed.
  * (Player is untouched -- nothing about raids is stored on it, so the
    feature adds no columns to the game's busiest table.)

Guild id is stored as a plain BigInteger with no foreign key, because
CascadeBot has no Guild table -- the bot has never needed to model a
server before. A raid is scoped to a guild purely by matching this
value, which is all the scoping the feature actually requires.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class GuildRaid(Base):
    """One raid instance in one Discord server."""

    __tablename__ = "guild_raids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # No FK -- see the module docstring. There is no Guild table.
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Enemy template name from bot/game/combat/enemies.py, plus the level
    # every copy of it is built at. Stored rather than re-rolled so the
    # boss a player fights on attack #7 is identical to the one fought on
    # attack #1, however long the raid runs.
    boss_name: Mapped[str] = mapped_column(String(64))
    boss_level: Mapped[int] = mapped_column(Integer, default=50)

    # The shared pool. current_hp is the ONLY piece of cross-player
    # mutable state in the game, and every write to it goes through
    # raid_service.record_attack_damage so the clamping rules live in
    # exactly one place.
    max_hp: Mapped[int] = mapped_column(BigInteger)
    current_hp: Mapped[int] = mapped_column(BigInteger)

    # "active" -> "defeated" (pool emptied) or "expired" (ran out of time).
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)

    tier: Mapped[str] = mapped_column(String(16), default="standard")

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ends_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    defeated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    participants: Mapped[list["RaidParticipant"]] = relationship(
        back_populates="raid", cascade="all, delete-orphan"
    )

    def hp_fraction(self) -> float:
        if self.max_hp <= 0:
            return 0.0
        return max(0.0, min(1.0, self.current_hp / self.max_hp))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GuildRaid id={self.id} guild={self.guild_id} boss={self.boss_name!r} {self.current_hp}/{self.max_hp}>"


class RaidParticipant(Base):
    """One player's involvement in one raid. Created lazily on their first
    attack, so a raid nobody has touched has no participant rows at all
    rather than one per server member."""

    __tablename__ = "raid_participants"
    __table_args__ = (
        UniqueConstraint("raid_id", "player_id", name="uq_raid_participant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raid_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("guild_raids.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )

    damage_dealt: Mapped[int] = mapped_column(BigInteger, default=0)

    # The hardest difficulty this player completed an attack at, used for
    # the absolute payout bonus (see raid_config.DIFFICULTY_REWARD_BONUS).
    # BEST rather than last or average, deliberately: a player who cleared
    # one Apex attack and then dropped to Standard because they ran out of
    # healing has demonstrably fought the hard version, and averaging
    # would quietly punish them for adapting.
    best_difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
    attacks_used: Mapped[int] = mapped_column(Integer, default=0)

    # Rewards are claimed explicitly rather than pushed automatically:
    # the raid can be defeated while a contributor is offline, and a
    # reward that arrived silently in their absence is a reward they
    # never notice they got.
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False)

    last_attack_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    raid: Mapped["GuildRaid"] = relationship(back_populates="participants")
    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RaidParticipant raid={self.raid_id} player={self.player_id} dmg={self.damage_dealt}>"
