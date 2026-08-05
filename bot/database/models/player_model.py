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
from typing import List, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

# Imported for type checkers only -- SQLAlchemy resolves these names from its
# own class registry at mapper-configuration time, so importing them at runtime
# would only create import cycles between the model modules.
if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.character_model import PlayerCharacter, SquadSlot
    from bot.database.models.economy_model import PlayerHarvester
    from bot.database.models.equipment_model import InventoryItem
    from bot.database.models.expedition_model import Expedition
    from bot.database.models.hq_model import PlayerBase, PlayerLootbox, PlayerShrine
    from bot.database.models.quest_model import PlayerQuest


class Player(Base):
    __tablename__ = "players"

    # Discord user ID doubles as the primary key -- one character per user for now.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(64))

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    shards: Mapped[int] = mapped_column(Integer, default=0)  # premium-ish currency: gacha, rare shop items

    # Reroll tokens: spent (alongside a flat, non-scaling gold cost) to
    # reroll an item's existing substats, or -- in much greater quantity --
    # to add a new substat slot beyond the 0-2 an item rolls with, up to a
    # max of 4. See bot/game/loot/rarity_config.py for exact costs.
    reroll_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Echoes: the duplicate currency (bot/game/economy/resonance_config.py).
    # Paid out by every duplicate character pull, and spent in the echo
    # exchange to buy a character OUTRIGHT. It exists so a gacha miss is
    # deterministic progress toward a hit rather than a consolation prize
    # of gold. Added by db_init._ensure_columns on an existing database,
    # same as the pity counters below.
    echoes: Mapped[int] = mapped_column(Integer, default=0)

    # Gear-upgrade materials, tiered common -> rare -> rarest. Spent
    # alongside gold to level up equipment (bot/game/loot/rarity_config.py).
    wood: Mapped[int] = mapped_column(Integer, default=0)
    stone: Mapped[int] = mapped_column(Integer, default=0)
    metal: Mapped[int] = mapped_column(Integer, default=0)
    crystal: Mapped[int] = mapped_column(Integer, default=0)
    xendium: Mapped[int] = mapped_column(Integer, default=0)
    permafrost_ore: Mapped[int] = mapped_column(Integer, default=0)
    void: Mapped[int] = mapped_column(Integer, default=0)
    entropy: Mapped[int] = mapped_column(Integer, default=0)

    # Character gacha pity counters (bot/game/economy/character_gacha_config.py,
    # bot/services/character_gacha_service.py). Each counts pulls SINCE the
    # last result of that rarity, so both are "how deep into the current
    # pity cycle am I" -- not lifetime totals. Persisted rather than held
    # per-session so a guarantee can't be dodged or lost by pulling across
    # a restart, and so single and 10x pulls share one continuous count.
    pity_since_five_star: Mapped[int] = mapped_column(Integer, default=0)
    pity_since_four_star: Mapped[int] = mapped_column(Integer, default=0)

    last_daily_claimed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Top.gg voting (bot/services/vote_service.py, bot/game/economy/
    # vote_config.py). Top.gg's API can only answer "has this user voted
    # in the last 12 hours?" -- it can't tell us whether we've already
    # paid out for THAT vote, so last_vote_claimed_at is what actually
    # prevents double-claiming inside one 12h window. vote_streak works
    # like daily_streak but per vote rather than per day (top.gg allows a
    # vote every 12h, so a player can advance it twice a day).
    last_vote_claimed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    vote_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_votes: Mapped[int] = mapped_column(Integer, default=0)

    # Quests -- see bot/database/models/quest_model.py::PlayerQuest and
    # bot/services/quest_service.py. beginner_quest_bonus_claimed guards
    # the one-time 300 shard bonus for finishing every beginner quest so
    # it can never be granted twice.
    # last_basic_quest_assigned_at is no longer read/written by
    # quest_service (basic quests now use per-row PlayerQuest.assigned_at
    # instead, since there can be several active at once -- a single
    # player-wide timestamp can't express that). Column stays here
    # unused rather than removed, since dropping it would be a schema
    # change.
    last_basic_quest_assigned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    beginner_quest_bonus_claimed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Domains (bot/game/economy/domain_config.py, bot/services/
    # domain_service.py): a regenerating energy resource spent on
    # single-battle "domain challenge" fights against a fixed enemy
    # squad, for direct on-demand rewards (materials/shards/gold/
    # lootboxes/XP) without running a full expedition. domain_energy is
    # the last-SAVED point count; domain_energy_updated_at is the anchor
    # domain_service regenerates real-time from -- same
    # accrue-since-last-checkpoint pattern as PlayerHarvester.
    # last_collected_at, except point-based (whole energy) rather than a
    # continuous rate, so the anchor advances by exact whole intervals
    # rather than jumping to "now" on every read (see domain_service's
    # module docstring for why that distinction matters here).
    domain_energy: Mapped[int] = mapped_column(Integer, default=120)
    domain_energy_updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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
    max_energy: Mapped[int] = mapped_column(Integer, default=50)  # ultimates trigger at 50 energy

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    inventory_items: Mapped[List["InventoryItem"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    expeditions: Mapped[List["Expedition"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    harvesters: Mapped[List["PlayerHarvester"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    base: Mapped["PlayerBase"] = relationship(
        back_populates="player", uselist=False, cascade="all, delete-orphan"
    )
    shrines: Mapped[List["PlayerShrine"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    lootboxes: Mapped[List["PlayerLootbox"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    characters: Mapped[List["PlayerCharacter"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    squad_slots: Mapped[List["SquadSlot"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    quests: Mapped[List["PlayerQuest"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )

    def xp_to_next_level(self) -> int:
        """simple curve: tune later once leveling design is locked in"""
        return 100 + (self.level - 1) * 50

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Player id={self.id} name={self.username!r} lvl={self.level}>"
