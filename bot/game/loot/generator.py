"""
The loot generator: given an ItemTemplate and a drop context (item level,
player luck), produces a fully-rolled InventoryItem instance ready to
`session.add()`.

Usage:

    from bot.game.loot.generator import LootGenerator

    gen = LootGenerator()
    item = gen.generate_item(template, player_id=player.id, item_level=14, luck=player.luck)
    session.add(item)

Every call is independent and randomized (optionally seedable for tests),
which is where the "a lot of variability" requirement comes from: two rolls
of the same template can differ in rarity, substat count, which substats,
their values, whether an ability shows up, and which one.
"""

from __future__ import annotations

import random

from bot.database.models.enums import Rarity
from bot.database.models.equipment_model import InventoryItem, ItemTemplate
from bot.game.loot import naming
from bot.game.loot.abilities import ACTIVE_ABILITIES, PASSIVE_ABILITIES, abilities_for_rarity
from bot.game.loot.rarity_config import (
    LUCK_SKEW_PER_POINT,
    RARITY_ABILITY_CHANCE,
    RARITY_BOTH_ABILITY_CHANCE,
    RARITY_STAT_MULTIPLIER,
    RARITY_SUBSTAT_COUNT,
    RARITY_WEIGHTS,
)
from bot.game.loot.stat_pools import SUBSTAT_POOL, roll_substat_value

_RARITY_ORDER = list(Rarity)  # Common -> Divine, index doubles as "tier"


class LootGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    # ------------------------------------------------------------------
    # Rarity
    # ------------------------------------------------------------------
    def roll_rarity(self, luck: int = 0) -> Rarity:
        """Weighted random rarity. Luck skews weight toward higher tiers,
        scaled by tier index so Divine benefits far more from luck than
        Uncommon does -- luck should feel like it hunts for the big drops,
        not inflate the whole curve evenly."""
        weights = []
        for tier_index, rarity in enumerate(_RARITY_ORDER):
            base = RARITY_WEIGHTS[rarity]
            skew = 1.0 + (luck * LUCK_SKEW_PER_POINT * tier_index)
            weights.append(base * skew)

        return self.rng.choices(_RARITY_ORDER, weights=weights, k=1)[0]

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

        candidates = [s for s in SUBSTAT_POOL if s != main_stat]
        chosen = self.rng.sample(candidates, k=min(count, len(candidates)))

        multiplier = RARITY_STAT_MULTIPLIER[rarity]
        return [
            {"stat": stat, "value": roll_substat_value(stat, item_level, multiplier, self.rng)}
            for stat in chosen
        ]

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------
    def roll_abilities(self, rarity: Rarity) -> tuple[dict | None, dict | None]:
        """Returns (active_ability, passive_ability); either may be None."""
        if self.rng.random() > RARITY_ABILITY_CHANCE[rarity]:
            return None, None

        available_active = abilities_for_rarity(ACTIVE_ABILITIES, rarity)
        available_passive = abilities_for_rarity(PASSIVE_ABILITIES, rarity)
        if not available_active and not available_passive:
            return None, None

        wants_both = self.rng.random() < RARITY_BOTH_ABILITY_CHANCE[rarity]

        if wants_both and available_active and available_passive:
            return self.rng.choice(available_active), self.rng.choice(available_passive)

        # Single ability: prefer whichever pool is non-empty, otherwise coin flip.
        if available_active and available_passive:
            if self.rng.random() < 0.5:
                return self.rng.choice(available_active), None
            return None, self.rng.choice(available_passive)
        if available_active:
            return self.rng.choice(available_active), None
        return None, self.rng.choice(available_passive)

    # ------------------------------------------------------------------
    # Full item
    # ------------------------------------------------------------------
    def generate_item(
        self,
        template: ItemTemplate,
        player_id: int,
        item_level: int = 1,
        luck: int = 0,
        rarity_override: Rarity | None = None,
    ) -> InventoryItem:
        rarity = rarity_override or self.roll_rarity(luck)

        main_stat_value = self.roll_main_stat(template, item_level, rarity)
        substats = self.roll_substats(template.main_stat, item_level, rarity)
        active_ability, passive_ability = self.roll_abilities(rarity)

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
            rarity=rarity,
            slot=template.slot,
            item_level=item_level,
            main_stat_type=template.main_stat,
            main_stat_value=main_stat_value,
            substats=substats,
            active_ability=active_ability,
            passive_ability=passive_ability,
            sockets=0,
            display_name=display_name,
        )
