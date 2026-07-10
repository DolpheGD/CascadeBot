"""
All the numbers that make rarity feel meaningfully different.

Nothing here talks to the database -- it's pure config, so game designers
(or you, later) can retune drop rates and power curves without touching
generator logic. (Luck was removed from the stat system, so rarity rolls
are no longer skewed by a player stat -- every roll uses RARITY_WEIGHTS as-is.)

Combat Overhaul changes:
  * Ancient rarity is gone -- Divine is now the ceiling.
  * Items start with 0-2 substats (RARITY_SUBSTAT_COUNT) instead of 0-4.
    Growing past that up to a max of 4 costs ADD_SUBSTAT_COST, which is
    much steeper than a plain REROLL_COST.
  * Reroll gold cost is FLAT per rarity -- it does not scale with how many
    times you've already rerolled that item, only the token cost does (via
    the rarity, not the reroll_count).
  * Every item has an UPGRADE_LEVEL_CAP by rarity; leveling stops there.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

# Relative drop weights (higher = more common).
RARITY_WEIGHTS: dict[Rarity, float] = {
    Rarity.COMMON: 42.0,
    Rarity.UNCOMMON: 26.0,
    Rarity.RARE: 15.0,
    Rarity.EPIC: 9.0,
    Rarity.LEGENDARY: 5.0,
    Rarity.MYTHIC: 2.5,
    Rarity.DIVINE: 0.5,
}

# Multiplier applied to main_stat and substat values. This is the primary
# lever for "epic items feel much stronger than common ones."
RARITY_STAT_MULTIPLIER: dict[Rarity, float] = {
    Rarity.COMMON: 1.0,
    Rarity.UNCOMMON: 1.15,
    Rarity.RARE: 1.35,
    Rarity.EPIC: 1.65,
    Rarity.LEGENDARY: 2.1,
    Rarity.MYTHIC: 2.9,
    Rarity.DIVINE: 4.0,
}

# (min, max) inclusive number of substats an item rolls with INITIALLY.
# Capped at 2 now regardless of rarity -- growing further is a deliberate,
# expensive player choice (see ADD_SUBSTAT_COST) rather than a roll.
RARITY_SUBSTAT_COUNT: dict[Rarity, tuple[int, int]] = {
    Rarity.COMMON: (0, 1),
    Rarity.UNCOMMON: (0, 2),
    Rarity.RARE: (1, 2),
    Rarity.EPIC: (1, 2),
    Rarity.LEGENDARY: (2, 2),
    Rarity.MYTHIC: (2, 2),
    Rarity.DIVINE: (2, 2),
}

# Hard ceiling on substat count for ANY item, reachable only by spending
# ADD_SUBSTAT_COST repeatedly.
MAX_SUBSTATS = 4

# Probability a WEAPON/ARTIFACT rolls its one active ability, or an
# ARMOR/ACCESSORY piece rolls its one passive ability. Epic and above always
# get one; lower rarities can still roll one, just simpler in effect.
RARITY_ABILITY_CHANCE: dict[Rarity, float] = {
    Rarity.COMMON: 0.05,
    Rarity.UNCOMMON: 0.18,
    Rarity.RARE: 0.35,
    Rarity.EPIC: 1.0,
    Rarity.LEGENDARY: 1.0,
    Rarity.MYTHIC: 1.0,
    Rarity.DIVINE: 1.0,
}

# Rarities at/above this index (see Rarity.sort_order) roll from the
# "complex" ability pool instead of the "simple" one -- see
# bot/game/loot/abilities.py. Epic = index 3.
COMPLEX_ABILITY_MIN_RARITY = Rarity.EPIC

# Max item_level (via item_upgrade_service.level_up) reachable per rarity.
UPGRADE_LEVEL_CAP: dict[Rarity, int] = {
    Rarity.COMMON: 5,
    Rarity.UNCOMMON: 10,
    Rarity.RARE: 16,
    Rarity.EPIC: 22,
    Rarity.LEGENDARY: 28,
    Rarity.MYTHIC: 34,
    Rarity.DIVINE: 40,
}

# Flat cost to reroll an item's EXISTING substats (does not add new ones,
# does not scale with reroll_count -- only rarity makes it pricier).
REROLL_COST: dict[Rarity, dict[str, int]] = {
    Rarity.COMMON: {"tokens": 2, "gold": 50},
    Rarity.UNCOMMON: {"tokens": 3, "gold": 100},
    Rarity.RARE: {"tokens": 5, "gold": 200},
    Rarity.EPIC: {"tokens": 8, "gold": 400},
    Rarity.LEGENDARY: {"tokens": 12, "gold": 800},
    Rarity.MYTHIC: {"tokens": 18, "gold": 1500},
    Rarity.DIVINE: {"tokens": 25, "gold": 3000},
}

# Cost to ADD one new substat slot (up to MAX_SUBSTATS). Deliberately much
# steeper than REROLL_COST at the same rarity -- growing an item's substat
# count is meant to be a rare, meaningful investment, not routine.
ADD_SUBSTAT_COST: dict[Rarity, dict[str, int]] = {
    Rarity.COMMON: {"tokens": 15, "gold": 300},
    Rarity.UNCOMMON: {"tokens": 25, "gold": 600},
    Rarity.RARE: {"tokens": 40, "gold": 1200},
    Rarity.EPIC: {"tokens": 65, "gold": 2500},
    Rarity.LEGENDARY: {"tokens": 100, "gold": 5000},
    Rarity.MYTHIC: {"tokens": 150, "gold": 9000},
    Rarity.DIVINE: {"tokens": 220, "gold": 16000},
}


def reroll_cost(rarity: Rarity) -> dict[str, int]:
    return REROLL_COST[rarity]


def add_substat_cost(rarity: Rarity) -> dict[str, int]:
    return ADD_SUBSTAT_COST[rarity]


def upgrade_level_cap(rarity: Rarity) -> int:
    return UPGRADE_LEVEL_CAP[rarity]
