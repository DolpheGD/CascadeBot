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
one -- all gated by the template's item_type (weapon/armor/artifact),
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
from bot.game.loot.stat_pools import (
    MAIN_STAT_GROWTH_PER_LEVEL,
    STAT_KEYS,
    roll_substat_value,
    roll_substat_value_type,
)

_RARITY_ORDER = list(Rarity)  # Common -> Divine, index doubles as "tier"


class LootGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    # ------------------------------------------------------------------
    # Rarity
    # ------------------------------------------------------------------
    def roll_rarity(self, max_rarity: Rarity | None = None, min_rarity: Rarity | None = None) -> Rarity:
        """Weighted random rarity. `max_rarity`, if given, strictly excludes
        anything above it from the pool -- used to cap drops by region
        difficulty (see bot/game/dungeon/region_config.py) so easier
        locations only ever produce lower-tier gear/lootboxes, while
        harder ones roll the full range (a mix of both, still weighted
        toward common). `min_rarity` similarly excludes anything below it
        -- used for a template's own tier floor (see ItemTemplate.min_rarity)
        so e.g. a Voidwalker-set piece never rolls plain Common."""
        weights_by_rarity = RARITY_WEIGHTS
        if max_rarity is not None:
            weights_by_rarity = {
                r: w for r, w in weights_by_rarity.items() if r.sort_order <= max_rarity.sort_order
            }
        if min_rarity is not None:
            weights_by_rarity = {
                r: w for r, w in weights_by_rarity.items() if r.sort_order >= min_rarity.sort_order
            }
        if not weights_by_rarity:
            # min_rarity above max_rarity (a region cap stricter than this
            # template's own floor) -- fall back to the template's floor
            # itself rather than producing nothing.
            return min_rarity or max_rarity or Rarity.COMMON
        rarities = list(weights_by_rarity.keys())
        weights = list(weights_by_rarity.values())
        return self.rng.choices(rarities, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Main stat
    # ------------------------------------------------------------------
    def roll_main_stat(
        self, template: ItemTemplate, item_level: int, rarity: Rarity
    ) -> float:
        multiplier = RARITY_STAT_MULTIPLIER[rarity]
        growth = MAIN_STAT_GROWTH_PER_LEVEL.get(template.main_stat, 1.0)
        value = (template.base_main_stat_value + (item_level - 1) * growth) * multiplier
        return round(value, 2)

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
        self, item_type: ItemType, rarity: Rarity, force: bool = False, linked_ability_id: str = "",
    ) -> tuple[dict | None, dict | None]:
        """Returns (active_ability, passive_ability); exactly one may be
        populated, both may be None. `force=True` skips the rarity's
        ability chance roll entirely (used by /admin_testgear so test items
        always come with an ability to try out). `linked_ability_id`, if
        given (see ItemTemplate.linked_ability_id), always uses that
        specific ability instead of a random one from the pool -- still
        subject to the rarity's ability-chance roll unless force is also
        set, but WHICH ability is no longer random."""
        if not force and self.rng.random() > RARITY_ABILITY_CHANCE[rarity]:
            return None, None

        if linked_ability_id:
            for pool, is_passive in ((WEAPON_SKILLS, False), (ARTIFACT_SKILLS, False),
                                      (ULTIMATE_ABILITIES, False), (ARMOR_PASSIVES, True)):
                for ability in pool:
                    if ability["id"] == linked_ability_id:
                        return (None, ability) if is_passive else (ability, None)
            # Unknown id -- fall through to the normal random roll rather
            # than silently giving nothing.

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
        max_rarity: Rarity | None = None,
    ) -> InventoryItem:
        if rarity_override is not None:
            rarity = rarity_override
        else:
            template_max = getattr(template, "max_rarity", None)
            effective_max = template_max if max_rarity is None else min(
                max_rarity, template_max or max_rarity, key=lambda r: r.sort_order
            )
            rarity = self.roll_rarity(
                max_rarity=effective_max, min_rarity=getattr(template, "min_rarity", None)
            )

        main_stat_value = self.roll_main_stat(template, item_level, rarity)
        substats = self.roll_substats(template.main_stat, item_level, rarity)
        active_ability, passive_ability = self.roll_ability(
            template.item_type, rarity, force=force_ability, linked_ability_id=template.linked_ability_id,
        )

        display_name = naming.generate_display_name(
            base_name=template.name,
            rarity=rarity,
            substats=substats,
            active_ability=active_ability,
            passive_ability=passive_ability,
            rng=self.rng,
            set_prefix=template.set_prefix,
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
