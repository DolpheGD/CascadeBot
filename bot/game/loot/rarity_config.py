"""
All the numbers that make rarity feel meaningfully different.

Nothing here talks to the database -- it's pure config, so game designers
(or you, later) can retune drop rates and power curves without touching
generator logic. (Luck was removed from the stat system, so rarity rolls
are no longer skewed by a player stat -- every roll uses RARITY_WEIGHTS as-is.)
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
    Rarity.MYTHIC: 2.2,
    Rarity.ANCIENT: 0.7,
    Rarity.DIVINE: 0.1,
}

# Multiplier applied to main_stat and substat values. This is the primary
# lever for "epic items feel much stronger than common ones."
RARITY_STAT_MULTIPLIER: dict[Rarity, float] = {
    Rarity.COMMON: 1.0,
    Rarity.UNCOMMON: 1.15,
    Rarity.RARE: 1.35,
    Rarity.EPIC: 1.65,
    Rarity.LEGENDARY: 2.1,
    Rarity.MYTHIC: 2.7,
    Rarity.ANCIENT: 3.5,
    Rarity.DIVINE: 5.0,
}

# (min, max) inclusive number of substats (0-4) rolled at each rarity.
RARITY_SUBSTAT_COUNT: dict[Rarity, tuple[int, int]] = {
    Rarity.COMMON: (0, 1),
    Rarity.UNCOMMON: (0, 2),
    Rarity.RARE: (1, 2),
    Rarity.EPIC: (1, 3),
    Rarity.LEGENDARY: (2, 3),
    Rarity.MYTHIC: (2, 4),
    Rarity.ANCIENT: (3, 4),
    Rarity.DIVINE: (4, 4),
}

# Probability a WEAPON/ARTIFACT rolls its one active ability, or an ARMOR
# piece rolls its one passive ability. SCROLLs ignore this entirely -- they
# always roll their ultimate ability (that's the whole point of the slot).
RARITY_ABILITY_CHANCE: dict[Rarity, float] = {
    Rarity.COMMON: 0.0,
    Rarity.UNCOMMON: 0.12,
    Rarity.RARE: 0.28,
    Rarity.EPIC: 0.50,
    Rarity.LEGENDARY: 0.75,
    Rarity.MYTHIC: 0.90,
    Rarity.ANCIENT: 1.0,
    Rarity.DIVINE: 1.0,
}
