"""
The loot generator: given an ItemTemplate and a drop context (item level),
produces a fully-rolled InventoryItem instance ready to `session.add()`.

Usage:

    from bot.game.loot.generator import LootGenerator

    gen = LootGenerator()
    item = gen.generate_item(template, player_id=player.id, item_level=14)
    session.add(item)

Every call is independent and randomized (optionally seedable for tests),
which is where "a lot of variability" comes from: two rolls of the same
template can differ in rarity, substat count, which substats, whether they
're flat or percent, their values, whether an ability shows up, and which
one -- all gated by the template's item_type (weapon/armor/artifact/scroll),
per the equipment design in bot/database/models/equipment_model.py.
"""

from __future__ import annotations

import random

from bot.database.models.enums import ItemType, Rarity
from bot.database.models.equipment_model import InventoryItem, ItemTemplate
from bot.game.loot import naming
from bot.game.loot.abilities import (
    ARMOR_PASSIVES,
    ARTIFACT_SKILLS,
    ULTIMATE_ABILITIES,
    WEAPON_SKILLS,
    abilities_for_rarity,
)
from bot.game.loot.rarity_config import (
    RARITY_ABILITY_CHANCE,
    RARITY_STAT_MULTIPLIER,
    RARITY_SUBSTAT_COUNT,
    RARITY_WEIGHTS,
)
from bot.game.loot.stat_pools import STAT_KEYS, roll_substat_value, roll_substat_value_type

_RARITY_ORDER = list(Rarity)  # Common -> Divine, index doubles as "tier"


class LootGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    # ------------------------------------------------------------------
    # Rarity
    # ------------------------------------------------------------------
    def roll_rarity(self) -> Rarity:
        """Weighted random rarity."""
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        return self.rng.choices(rarities, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Main stat
    # ------------------------------------------------------------------
    def roll_main_stat(
        self, template: ItemTemplate, item_level: int, rarity: Rarity
    ) -> float:
        multiplier = RARITY_STAT_MULTIPLIER[rarity]
        # Base value grows ~linearly with item level off the template's
        # level-1 value; tune the +1.0/level growth rate here later.
        value = (template.base_main_stat_value + (item_level - 1) * 1.0) * multiplier
        return round(value, 1)

    # ------------------------------------------------------------------
    # Substats
    # ------------------------------------------------------------------
    def roll_substats(
        self, main_stat: str, item_level: int, rarity: Rarity
    ) -> list[dict]:
        lo, hi = RARITY_SUBSTAT_COUNT[rarity]
        count = self.rng.randint(lo, hi)
        if count == 0:
            return []

        candidates = [s for s in STAT_KEYS if s != main_stat]
        chosen = self.rng.sample(candidates, k=min(count, len(candidates)))

        multiplier = RARITY_STAT_MULTIPLIER[rarity]
        substats = []
        for stat in chosen:
            value_type = roll_substat_value_type(stat, self.rng)
            value = roll_substat_value(stat, value_type, item_level, multiplier, self.rng)
            substats.append({"stat": stat, "value": value, "value_type": value_type})
        return substats

    # ------------------------------------------------------------------
    # Abilities -- which pool (and whether active vs passive) depends on
    # item_type, per the equipment design.
    # ------------------------------------------------------------------
    def roll_ability(
        self, item_type: ItemType, rarity: Rarity, force: bool = False
    ) -> tuple[dict | None, dict | None]:
        """Returns (active_ability, passive_ability); exactly one may be
        populated, both may be None (except SCROLL, which always gets an
        active ultimate ability). `force=True` skips the rarity's ability
        chance roll entirely (used by /admin_testgear so test items always
        come with an ability to try out)."""
        if item_type == ItemType.SCROLL:
            pool = abilities_for_rarity(ULTIMATE_ABILITIES, rarity) or ULTIMATE_ABILITIES
            return self.rng.choice(pool), None

        if not force and self.rng.random() > RARITY_ABILITY_CHANCE[rarity]:
            return None, None

        if item_type == ItemType.WEAPON:
            pool = abilities_for_rarity(WEAPON_SKILLS, rarity)
            return (self.rng.choice(pool), None) if pool else (None, None)
        if item_type == ItemType.ARTIFACT:
            pool = abilities_for_rarity(ARTIFACT_SKILLS, rarity)
            return (self.rng.choice(pool), None) if pool else (None, None)
        if item_type == ItemType.ARMOR:
            pool = abilities_for_rarity(ARMOR_PASSIVES, rarity)
            return (None, self.rng.choice(pool)) if pool else (None, None)

        return None, None

    # ------------------------------------------------------------------
    # Full item
    # ------------------------------------------------------------------
    def generate_item(
        self,
        template: ItemTemplate,
        player_id: int,
        item_level: int = 1,
        rarity_override: Rarity | None = None,
        force_ability: bool = False,
    ) -> InventoryItem:
        rarity = rarity_override or self.roll_rarity()

        main_stat_value = self.roll_main_stat(template, item_level, rarity)
        # Scrolls are pure ultimate-carriers -- no substat noise.
        substats = (
            [] if template.item_type == ItemType.SCROLL
            else self.roll_substats(template.main_stat, item_level, rarity)
        )
        active_ability, passive_ability = self.roll_ability(template.item_type, rarity, force=force_ability)

        if template.item_type == ItemType.SCROLL:
            # Scroll base names are already complete phrases ("Scroll of
            # the Meteor") -- running them through the prefix/suffix
            # namer would double up ("...of the Meteor of Might").
            display_name = template.name
        else:
            display_name = naming.generate_display_name(
                base_name=template.name,
                rarity=rarity,
                substats=substats,
                active_ability=active_ability,
                passive_ability=passive_ability,
                rng=self.rng,
            )

        return InventoryItem(
            player_id=player_id,
            template_id=template.id,
            item_type=template.item_type,
            rarity=rarity,
            slot=template.slot,
            item_level=item_level,
            main_stat_type=template.main_stat,
            main_stat_value=main_stat_value,
            substats=substats,
            active_ability=active_ability,
            passive_ability=passive_ability,
            display_name=display_name,
        )
