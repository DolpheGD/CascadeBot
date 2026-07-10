"""
Passive income: HarvesterTemplate is the hand-authored catalog ("Gold Mine",
"Shard Well"). PlayerHarvester is one player's owned copy -- level and
last_collected_at live here so upgrading/collecting never touches the
template.

Production accrues over real time between collections, capped at
`max_accumulation_hours` so idling doesn't let a player stockpile forever
without checking in (see bot/services/harvester_service.py for the math).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base


class HarvesterTemplate(Base):
    __tablename__ = "harvester_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")

    currency: Mapped[str] = mapped_column(String(16))  # "gold" or "shards"
    unlock_cost: Mapped[int] = mapped_column(Integer, default=0)
    unlock_currency: Mapped[str] = mapped_column(String(16), default="gold")

    base_rate_per_hour: Mapped[float] = mapped_column(Float, default=1.0)
    # production_rate(level) = base_rate_per_hour * (level ** level_scaling_exponent)
    # 1.0 = linear (unchanged old behavior); below 1.0 = diminishing returns
    # per level, used to keep rarer currencies (Shards) from scaling too
    # fast off upgrades alone.
    level_scaling_exponent: Mapped[float] = mapped_column(Float, default=1.0)
    max_level: Mapped[int] = mapped_column(Integer, default=10)
    max_accumulation_hours: Mapped[float] = mapped_column(Float, default=8.0)

    # upgrade cost at a given level = base_upgrade_cost * (upgrade_cost_growth ** (level - 1))
    base_upgrade_cost: Mapped[int] = mapped_column(Integer, default=100)
    upgrade_cost_growth: Mapped[float] = mapped_column(Float, default=1.5)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HarvesterTemplate {self.name!r} currency={self.currency}>"


class PlayerHarvester(Base):
    __tablename__ = "player_harvesters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("harvester_templates.id"))

    level: Mapped[int] = mapped_column(Integer, default=1)
    last_collected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="harvesters")  # noqa: F821
    template: Mapped["HarvesterTemplate"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerHarvester template_id={self.template_id} level={self.level}>"


class LootboxTemplate(Base):
    __tablename__ = "lootbox_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier: Mapped[str] = mapped_column(String(16), unique=True)  # common/uncommon/rare/epic/legendary/mythic
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")

    min_gold: Mapped[int] = mapped_column(Integer, default=0)
    max_gold: Mapped[int] = mapped_column(Integer, default=0)
    min_shards: Mapped[int] = mapped_column(Integer, default=0)
    max_shards: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=1)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LootboxTemplate {self.tier}>"


class PlayerLootbox(Base):
    __tablename__ = "player_lootboxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("lootbox_templates.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    player: Mapped["Player"] = relationship(back_populates="lootboxes")  # noqa: F821
    template: Mapped["LootboxTemplate"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerLootbox template_id={self.template_id} quantity={self.quantity}>"
