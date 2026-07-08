"""
Player = the "permanent progression" loop.

Everything here persists forever: level, base stats, gold. This is
deliberately separate from expedition state (expedition_model.py), which is
thrown away when a run ends.

Stat design (per project spec): HP, ATK, DEF, MP (max mana), ELE (elemental
damage), SPD, plus Crit Rate% / Crit Damage% and Recharge (energy AND mana
gained per basic attack). No class, no reputation, no Luck, no Dodge --
combat never has a miss chance.
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

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    shards: Mapped[int] = mapped_column(Integer, default=0)  # premium-ish currency: gacha, rare shop items

    last_daily_claimed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Base stats -- equipment/artifacts/buffs modify these at combat time,
    # they don't overwrite them here.
    max_hp: Mapped[int] = mapped_column(Integer, default=100)
    attack: Mapped[int] = mapped_column(Integer, default=10)
    defense: Mapped[int] = mapped_column(Integer, default=10)
    max_mana: Mapped[int] = mapped_column(Integer, default=50)
    elemental: Mapped[int] = mapped_column(Integer, default=10)   # ELE -- elemental damage stat
    speed: Mapped[int] = mapped_column(Integer, default=10)       # SPD -- turn gauge fill rate
    crit_rate: Mapped[int] = mapped_column(Integer, default=5)     # percent
    crit_damage: Mapped[int] = mapped_column(Integer, default=150)  # percent
    recharge: Mapped[int] = mapped_column(Integer, default=5)     # energy AND mana gained per basic attack
    max_energy: Mapped[int] = mapped_column(Integer, default=100)  # ultimates trigger at 100 energy

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    inventory_items: Mapped[List["InventoryItem"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    expeditions: Mapped[List["Expedition"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    harvesters: Mapped[List["PlayerHarvester"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )
    lootboxes: Mapped[List["PlayerLootbox"]] = relationship(  # noqa: F821
        back_populates="player", cascade="all, delete-orphan"
    )

    def xp_to_next_level(self) -> int:
        """simple curve: tune later once leveling design is locked in"""
        return 100 + (self.level - 1) * 50

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Player id={self.id} name={self.username!r} lvl={self.level}>"
