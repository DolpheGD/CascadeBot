"""
Upgrade path for items the player already owns. Built first: reroll and
level-up. Left as clear extension points for later: socket upgrades and
adding/upgrading an ability slot post-drop (e.g. via a rare crafting
material) -- the DB columns (`sockets`, `active_ability`, `passive_ability`)
already support it, they're just not wired to a currency/material cost yet.

Both functions mutate the InventoryItem in place (same `id`, so equipped
state and history are preserved) rather than generating a new item.
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import InventoryItem
from bot.game.loot import naming
from bot.game.loot.rarity_config import RARITY_STAT_MULTIPLIER, RARITY_SUBSTAT_COUNT
from bot.game.loot.stat_pools import SUBSTAT_POOL, roll_substat_value


def reroll_substats(item: InventoryItem, rng: random.Random | None = None) -> InventoryItem:
    """Re-roll every substat on `item`, keeping the same count (unless the
    rarity's range has since changed) but with fresh stats and values.
    Increments reroll_count so future costs/limits can scale with it."""
    rng = rng or random.Random()

    lo, hi = RARITY_SUBSTAT_COUNT[item.rarity]
    count = max(lo, min(len(item.substats) or lo, hi)) if item.substats else rng.randint(lo, hi)

    candidates = [s for s in SUBSTAT_POOL if s != item.main_stat_type]
    chosen = rng.sample(candidates, k=min(count, len(candidates)))

    multiplier = RARITY_STAT_MULTIPLIER[item.rarity]
    item.substats = [
        {"stat": stat, "value": roll_substat_value(stat, item.item_level, multiplier, rng)}
        for stat in chosen
    ]
    item.reroll_count += 1

    item.display_name = naming.generate_display_name(
        base_name=item.template.name,
        rarity=item.rarity,
        substats=item.substats,
        active_ability=item.active_ability,
        passive_ability=item.passive_ability,
        rng=rng,
    )
    return item


def level_up(item: InventoryItem, levels: int = 1) -> InventoryItem:
    """Raise item_level and rescale main stat + existing substats to match.
    Does not change rarity, substat count, or which substats are present --
    it makes the item you already have stronger, it doesn't reroll it."""
    if levels <= 0:
        raise ValueError("levels must be positive")

    new_level = item.item_level + levels
    multiplier = RARITY_STAT_MULTIPLIER[item.rarity]

    template = item.template
    item.main_stat_value = round(
        (template.base_main_stat_value + (new_level - 1) * 1.0) * multiplier, 1
    )

    rescaled = []
    for sub in item.substats:
        lo, hi = SUBSTAT_POOL[sub["stat"]]
        # Preserve the substat's original roll "luck" (where in its range it
        # landed) rather than rerolling it, so leveling up doesn't also
        # gamble the substat higher or lower.
        old_per_level_range = (hi - lo) or 1.0
        old_level = max(item.item_level, 1)
        implied_roll = sub["value"] / (old_level * multiplier)
        roll_fraction = max(0.0, min(1.0, (implied_roll - lo) / old_per_level_range))
        new_per_level = lo + roll_fraction * (hi - lo)
        rescaled.append(
            {"stat": sub["stat"], "value": round(new_per_level * new_level * multiplier, 1)}
        )
    item.substats = rescaled
    item.item_level = new_level
    return item
