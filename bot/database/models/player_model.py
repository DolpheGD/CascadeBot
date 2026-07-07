"""
Player = the "permanent progression" loop.

Everything here persists forever: level, base stats, gold, reputation,
unlocked classes. This is deliberately separate from expedition state
(expedition_model.py), which is thrown away when a run ends.
"""

from __future__ import annotations

import datetime as dt
from typing import List

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base


class Player(Base):
    __tablename__ = "players"

    # Discord user ID doubles as the primary key -- one character per user for now.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(64))

    class_name: Mapped[str] = mapped_column(String(32), default="Wanderer")
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    shards: Mapped[int] = mapped_column(Integer, default=0)  # premium-ish currency: gacha, rare shop items
    reputation: Mapped[int] = mapped_column(Integer, default=0)

    last_daily_claimed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Base stats -- equipment/artifacts/buffs modify these at combat time,
    # they don't overwrite them here.
    max_hp: Mapped[int] = mapped_column(Integer, default=100)
    max_mana: Mapped[int] = mapped_column(Integer, default=100)
    max_energy: Mapped[int] = mapped_column(Integer, default=100)
    attack: Mapped[int] = mapped_column(Integer, default=10)
    defense: Mapped[int] = mapped_column(Integer, default=10)
    magic: Mapped[int] = mapped_column(Integer, default=10)
    speed: Mapped[int] = mapped_column(Integer, default=10)
    luck: Mapped[int] = mapped_column(Integer, default=5)
    crit_chance: Mapped[int] = mapped_column(Integer, default=5)   # percent
    crit_damage: Mapped[int] = mapped_column(Integer, default=150)  # percent
    dodge: Mapped[int] = mapped_column(Integer, default=5)          # percent
    healing_bonus: Mapped[int] = mapped_column(Integer, default=0)  # percent

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    inventory_items: Mapped[List["InventoryItem"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["PlayerArtifact"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    expeditions: Mapped[List["Expedition"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    harvesters: Mapped[List["PlayerHarvester"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )

    def xp_to_next_level(self) -> int:
        """simple curve: tune later once leveling design is locked in"""
        return 100 + (self.level - 1) * 50

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Player id={self.id} name={self.username!r} lvl={self.level}>"
