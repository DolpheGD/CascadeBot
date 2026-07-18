"""
Equipment: the static catalog (ItemTemplate) and rolled, owned drops
(InventoryItem) that make up the "equipment progression" loop.

Combat Overhaul changes:
  * Only four slot TYPES exist now (WEAPON, ARTIFACT, ARMOR, ACCESSORY) --
    see bot/database/models/enums.py::EquipmentSlot and SLOT_CAPACITY.
    WEAPON and ARTIFACT hold one item; ARMOR and ACCESSORY each hold two.
    The old primary/secondary weapon-and-artifact pairing and the SCROLL
    slot are gone; ultimates come from the character's kit instead of gear.
  * Equipment is now equipped PER CHARACTER (InventoryItem.character_id),
    not per player -- each of your 4 squad members has their own loadout.
  * Items start with 0-2 substats instead of 0-4. Growing beyond that (up
    to a max of 4) costs a separate, much larger "add substat" spend of
    reroll tokens (see rarity_config.ADD_SUBSTAT_COST) -- a plain reroll
    only re-rolls the substats you already have.
  * Artifacts can now main-stat into HP or DEF, not just offense/utility.

    Base Item (ItemTemplate) -> Rarity -> Main stat -> Substats (0-2 base,
    up to 4 with Substat Catalyst spend) -> Ability roll -> Name

  * WEAPON: main stat is attack or elemental. May roll ONE active ability
    (a "weapon skill"). No passives.
  * ARMOR: main stat is defense, health, speed, energy (recharge), or mana.
    May roll ONE passive ability. No actives.
  * ACCESSORY: main stat is defense, health, speed, energy (recharge), mana,
    crit rate, or crit damage. May roll ONE passive ability. No actives.
  * ARTIFACT: main stat is speed, energy (recharge), attack, elemental,
    crit damage, crit rate, HP, or DEF. May roll ONE active ability (an
    "artifact skill"). No passives.

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

    # Item sets: a handful of templates belong to a themed set (Wood, Iron,
    # Sigma Wolf, Crystal, Xendium, Permafrost, Hi-Tech, Error Code,
    # Voidwalker, Entropic, Refense, and the ultra-rare "500 Billian Gem
    # Giveaway"). set_prefix is what actually shows up in the generated
    # display name (see bot/game/loot/naming.py) -- kept separate from
    # set_name so the display prefix can be shorter/cleaner than the full
    # set name if needed. Empty string ("" ) means "not part of a set" --
    # those items get a plain rarity-flavored generic prefix instead.
    set_name: Mapped[str] = mapped_column(String(64), default="")
    set_prefix: Mapped[str] = mapped_column(String(32), default="")

    # If set, every instance of this template ALWAYS rolls this specific
    # ability (by id, looked up across every pool in
    # bot/game/loot/abilities.py) instead of a random one from its
    # item_type's pool -- "certain items will be linked to certain
    # abilities or passives." Still subject to RARITY_ABILITY_CHANCE
    # unless force_ability is also passed to the generator.
    linked_ability_id: Mapped[str] = mapped_column(String(64), default="")

    # Deliberately excluded from normal random template rolls -- see
    # bot/services/item_template_service.py::pick_random_template(). Only
    # the joke-tier "500 Billian Gem Giveaway" set uses this.
    is_ultra_rare: Mapped[bool] = mapped_column(Boolean, default=False)

    # The rarity WINDOW this template can ever roll, inclusive -- a
    # material/craftsmanship ceiling (and floor), independent of the
    # is_ultra_rare gate above. Leather is always going to be Common/
    # Uncommon no matter how lucky the roll is; a Voidwalker-set piece is
    # never going to show up as plain Common. Enforced in
    # LootGenerator.generate_item() (as a safety net for every path) and,
    # for actual random template SELECTION, in
    # item_template_service.pick_random_template()'s optional `rarity`
    # filter (so a roll that already landed on a high rarity picks from
    # templates that can actually produce it, rather than picking any
    # template and then clamping down after the fact).
    min_rarity: Mapped[Rarity] = mapped_column(default=Rarity.COMMON)
    max_rarity: Mapped[Rarity] = mapped_column(default=Rarity.DIVINE)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ItemTemplate {self.name!r} slot={self.slot} main_stat={self.main_stat}>"


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("item_templates.id"))

    # Which owned character (if any) has this equipped. NULL = sitting
    # unequipped in the player's shared inventory. A character can hold at
    # most SLOT_CAPACITY[slot] items per EquipmentSlot (1 for WEAPON/
    # ARTIFACT, 2 for ARMOR/ACCESSORY) -- enforced in inventory_service,
    # not at the DB layer, so we can give clean error messages.
    character_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("player_characters.id", ondelete="SET NULL"), nullable=True
    )

    item_type: Mapped[ItemType] = mapped_column(default=ItemType.WEAPON)
    rarity: Mapped[Rarity] = mapped_column(default=Rarity.COMMON)
    slot: Mapped[EquipmentSlot] = mapped_column()
    item_level: Mapped[int] = mapped_column(Integer, default=1)

    main_stat_type: Mapped[str] = mapped_column(String(32))
    main_stat_value: Mapped[float] = mapped_column(Integer, default=0)

    # [{"stat": "crit_rate", "value": 8.0, "value_type": "flat"}, ...] --
    # 0 to 2 entries on roll, growable up to 4 via a Substat Catalyst spend
    # (bot/services/item_upgrade_service.py::add_substat). value_type is
    # "flat" (added directly) or "percent" (percent of the CHARACTER'S BASE
    # stat, computed once and added as a flat bonus -- percent substats
    # never compound with other equipped items).
    substats: Mapped[list] = mapped_column(JSON, default=list)

    # Only one of these is ever populated, depending on item_type:
    # weapon/artifact -> active_ability, armor/accessory -> passive_ability.
    active_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    passive_ability: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    display_name: Mapped[str] = mapped_column(String(96))  # e.g. "Savage Iron Sword of Chaos"

    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    reroll_count: Mapped[int] = mapped_column(Integer, default=0)

    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="inventory_items")  # noqa: F821
    template: Mapped["ItemTemplate"] = relationship()
    character: Mapped["PlayerCharacter | None"] = relationship(back_populates="equipped_items")  # noqa: F821

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
        to be applied against the character's base stat by the caller)."""
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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InventoryItem {self.display_name!r} rarity={self.rarity}>"
