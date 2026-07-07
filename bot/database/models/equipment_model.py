"""
Equipment: the static catalog (ItemTemplate) and rolled, owned drops
(InventoryItem) that make up the "equipment progression" loop.

    Base Item (ItemTemplate) -> Rarity -> Substats (0-4) -> Ability roll -> Name

ItemTemplate is hand-authored design-time data (one row per base item, e.g.
"Iron Sword"). InventoryItem is what the loot generator
(bot/game/loot/generator.py) creates per-drop: two players who loot the same
template end up with different InventoryItem rows because rarity, substats,
and abilities are rolled independently each time.
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
    item_type: Mapped[ItemType] = mapped_column(default=ItemType.EQUIPMENT)
    slot: Mapped[EquipmentSlot] = mapped_column()

    # The one stat every instance of this template guarantees, e.g. "attack"
    # for a sword, "defense" for a shield, "magic" for a staff. Must be a key
    # from bot.game.loot.stat_pools.STAT_KEYS.
    main_stat: Mapped[str] = mapped_column(String(32))
    # Value of that main stat at item_level 1, Common rarity. The generator
    # scales this up by level and rarity multiplier.
    base_main_stat_value: Mapped[int] = mapped_column(Integer, default=10)

    max_sockets: Mapped[int] = mapped_column(Integer, default=0)
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

    rarity: Mapped[Rarity] = mapped_column(default=Rarity.COMMON)
    slot: Mapped[EquipmentSlot] = mapped_column()
    item_level: Mapped[int] = mapped_column(Integer, default=1)
    quality: Mapped[int] = mapped_column(Integer, default=100)  # percent, 0-100+

    main_stat_type: Mapped[str] = mapped_column(String(32))
    main_stat_value: Mapped[float] = mapped_column(Integer, default=0)

    # [{"stat": "crit_chance", "value": 8.0}, ...] -- 0 to 4 entries.
    substats: Mapped[list] = mapped_column(JSON, default=list)

    # Nullable ability payloads. See bot/game/loot/abilities.py for shape.
    active_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    passive_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sockets: Mapped[int] = mapped_column(Integer, default=0)
    display_name: Mapped[str] = mapped_column(String(96))  # e.g. "Savage Iron Sword of Chaos"

    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    reroll_count: Mapped[int] = mapped_column(Integer, default=0)

    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="inventory_items")  # noqa: F821
    template: Mapped["ItemTemplate"] = relationship()

    def total_stat_bonus(self, stat: str) -> float:
        """sum contribution of `stat` from main stat + substats combined"""
        total = self.main_stat_value if self.main_stat_type == stat else 0.0
        total += sum(s["value"] for s in self.substats if s.get("stat") == stat)
        return total

    def has_ability(self) -> bool:
        return self.active_ability is not None or self.passive_ability is not None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InventoryItem {self.display_name!r} rarity={self.rarity}>"
