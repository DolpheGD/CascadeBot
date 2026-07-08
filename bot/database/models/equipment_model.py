"""
Equipment: the static catalog (ItemTemplate) and rolled, owned drops
(InventoryItem) that make up the "equipment progression" loop. This single
system now covers weapons, armor, artifacts, AND scrolls (the ultimate
carrier) -- they all roll the same way (rarity -> main stat -> substats ->
ability), just with different main-stat pools and ability rules per
item_type:

    Base Item (ItemTemplate) -> Rarity -> Main stat -> Substats (0-4) ->
    Ability roll -> Name

  * WEAPON: main stat is attack or elemental. May roll ONE active ability
    (a "weapon skill"). No passives.
  * ARMOR (helmet/necklace, chest, leggings, boots): main stat is defense,
    health, speed, energy (recharge), or mana. May roll ONE passive
    ability. No actives -- armor is passive-only by design.
  * ARTIFACT: main stat is speed, energy (recharge), attack, elemental,
    crit damage, or crit rate. May roll ONE active ability (an "artifact
    skill"). No passives.
  * SCROLL: always carries exactly one ultimate ability. Small main stat
    for flavor, no substats.

ItemTemplate is hand-authored design-time data (one row per base item, e.g.
"Iron Sword"). InventoryItem is what the loot generator
(bot/game/loot/generator.py) creates per-drop: two players who loot the same
template end up with different InventoryItem rows because rarity, substats,
and ability are rolled independently each time.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base
from bot.database.models.enums import EquipmentSlot, ItemType, Rarity


class ItemTemplate(Base):
    __tablename__ = "item_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    item_type: Mapped[ItemType] = mapped_column(default=ItemType.WEAPON)
    slot: Mapped[EquipmentSlot] = mapped_column()

    # The one stat every instance of this template guarantees, e.g. "attack"
    # for a sword, "defense" for a shield, "elemental" for a staff. Must be
    # a key from bot.game.loot.stat_pools.STAT_KEYS.
    main_stat: Mapped[str] = mapped_column(String(32))
    # Value of that main stat at item_level 1, Common rarity. The generator
    # scales this up by level and rarity multiplier.
    base_main_stat_value: Mapped[int] = mapped_column(Integer, default=10)

    flavor_text: Mapped[str] = mapped_column(String(256), default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ItemTemplate {self.name!r} slot={self.slot} main_stat={self.main_stat}>"


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("item_templates.id"))

    item_type: Mapped[ItemType] = mapped_column(default=ItemType.WEAPON)
    rarity: Mapped[Rarity] = mapped_column(default=Rarity.COMMON)
    slot: Mapped[EquipmentSlot] = mapped_column()
    item_level: Mapped[int] = mapped_column(Integer, default=1)

    main_stat_type: Mapped[str] = mapped_column(String(32))
    main_stat_value: Mapped[float] = mapped_column(Integer, default=0)

    # [{"stat": "crit_rate", "value": 8.0, "value_type": "flat"}, ...] --
    # 0 to 4 entries. value_type is "flat" (added directly) or "percent"
    # (percent of the PLAYER'S BASE stat, computed once and added as a flat
    # bonus -- percent substats never compound with other gear).
    substats: Mapped[list] = mapped_column(JSON, default=list)

    # Only one of these is ever populated, depending on item_type:
    # weapon/artifact/scroll -> active_ability, armor -> passive_ability.
    # Kept as two columns (rather than one polymorphic one) so combat code
    # can keep reading "every active ability" / "every passive ability"
    # uniformly regardless of source slot.
    active_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    passive_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    display_name: Mapped[str] = mapped_column(String(96))  # e.g. "Savage Iron Sword of Chaos"

    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    # For capacity-2 slots (WEAPON, ARTIFACT): 0 = primary/first, 1 =
    # secondary/second. Meaningless (always 0) for capacity-1 slots.
    equip_slot_index: Mapped[int] = mapped_column(Integer, default=0)
    reroll_count: Mapped[int] = mapped_column(Integer, default=0)

    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="inventory_items")  # noqa: F821
    template: Mapped["ItemTemplate"] = relationship()

    def total_stat_bonus_flat(self, stat: str) -> float:
        """Sum of every FLAT contribution to `stat` from main stat + flat substats."""
        total = self.main_stat_value if self.main_stat_type == stat else 0.0
        total += sum(
            s["value"] for s in self.substats
            if s.get("stat") == stat and s.get("value_type", "flat") == "flat"
        )
        return total

    def percent_substats_for(self, stat: str) -> float:
        """Sum of every PERCENT substat contribution to `stat` (percentage points,
        to be applied against the player's base stat by the caller)."""
        return sum(
            s["value"] for s in self.substats
            if s.get("stat") == stat and s.get("value_type") == "percent"
        )

    def total_stat_bonus(self, stat: str) -> float:
        """Back-compat helper: flat-only total (used by simple display code
        that doesn't need the base-stat-aware percent split)."""
        return self.total_stat_bonus_flat(stat)

    def has_ability(self) -> bool:
        return self.active_ability is not None or self.passive_ability is not None

    def is_ultimate(self) -> bool:
        return self.item_type == ItemType.SCROLL

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InventoryItem {self.display_name!r} rarity={self.rarity}>"
