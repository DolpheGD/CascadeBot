"""
Upgrade path for items the player already owns: reroll and level-up. Both
functions mutate the InventoryItem in place (same `id`, so equipped state
is preserved) rather than generating a new item.
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import InventoryItem
from bot.game.loot import naming
from bot.game.loot.rarity_config import MAX_SUBSTATS, RARITY_STAT_MULTIPLIER
from bot.game.loot.stat_pools import STAT_KEYS, roll_substat_value, roll_substat_value_type


def reroll_substats(item: InventoryItem, rng: random.Random | None = None) -> InventoryItem:
    """Re-roll every substat CURRENTLY on `item` (fresh stats, flat/percent
    types, and values) without changing how many it has. Use add_substat()
    to grow the count instead. Increments reroll_count for record-keeping."""
    rng = rng or random.Random()

    count = len(item.substats)
    if count == 0:
        return item

    candidates = [s for s in STAT_KEYS if s != item.main_stat_type]
    chosen = rng.sample(candidates, k=min(count, len(candidates)))

    multiplier = RARITY_STAT_MULTIPLIER[item.rarity]
    substats = []
    for stat in chosen:
        value_type = roll_substat_value_type(stat, rng)
        value = roll_substat_value(stat, value_type, item.item_level, multiplier, rng)
        substats.append({"stat": stat, "value": value, "value_type": value_type})
    item.substats = substats
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


def add_substat(item: InventoryItem, rng: random.Random | None = None) -> InventoryItem:
    """Grow `item`'s substat count by exactly one, up to MAX_SUBSTATS. The
    caller (item_upgrade_service) is responsible for charging the much
    steeper ADD_SUBSTAT_COST before calling this -- this function assumes
    the spend already happened and just does the roll."""
    rng = rng or random.Random()
    if len(item.substats) >= MAX_SUBSTATS:
        return item

    taken = {s["stat"] for s in item.substats} | {item.main_stat_type}
    candidates = [s for s in STAT_KEYS if s not in taken]
    if not candidates:
        return item

    stat = rng.choice(candidates)
    multiplier = RARITY_STAT_MULTIPLIER[item.rarity]
    value_type = roll_substat_value_type(stat, rng)
    value = roll_substat_value(stat, value_type, item.item_level, multiplier, rng)
    item.substats = [*item.substats, {"stat": stat, "value": value, "value_type": value_type}]

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
        value_type = sub.get("value_type", "flat")
        from bot.game.loot.stat_pools import FLAT_SUBSTAT_POOL, PERCENT_SUBSTAT_POOL
        pool = PERCENT_SUBSTAT_POOL if value_type == "percent" else FLAT_SUBSTAT_POOL
        lo, hi = pool[sub["stat"]]
        # Preserve the substat's original roll "luck" (where in its range it
        # landed) rather than rerolling it, so leveling up doesn't also
        # gamble the substat higher or lower.
        old_per_level_range = (hi - lo) or 1.0
        old_level = max(item.item_level, 1)
        implied_roll = sub["value"] / (old_level * multiplier)
        roll_fraction = max(0.0, min(1.0, (implied_roll - lo) / old_per_level_range))
        new_per_level = lo + roll_fraction * (hi - lo)
        rescaled.append({
            "stat": sub["stat"],
            "value": round(new_per_level * new_level * multiplier, 2 if value_type == "percent" else 1),
            "value_type": value_type,
        })
    item.substats = rescaled
    item.item_level = new_level
    return item
