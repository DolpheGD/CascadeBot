"""
All the numbers that make rarity feel meaningfully different.

Nothing here talks to the database -- it's pure config, so game designers
(or you, later) can retune drop rates and power curves without touching
generator logic.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

# Relative drop weights (higher = more common). Luck shifts these at roll
# time -- see generator.roll_rarity().
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

# Probability an item rolls at least one ability (active and/or passive).
RARITY_ABILITY_CHANCE: dict[Rarity, float] = {
    Rarity.COMMON: 0.0,
    Rarity.UNCOMMON: 0.05,
    Rarity.RARE: 0.15,
    Rarity.EPIC: 0.35,
    Rarity.LEGENDARY: 0.65,
    Rarity.MYTHIC: 0.85,
    Rarity.ANCIENT: 0.95,
    Rarity.DIVINE: 1.0,
}

# Given an item HAS an ability, chance it rolls BOTH active and passive
# instead of just one. Gated behind rarity so "both" feels earned --
# "an item can provide an active, a passive, or both if it is powerful enough."
RARITY_BOTH_ABILITY_CHANCE: dict[Rarity, float] = {
    Rarity.COMMON: 0.0,
    Rarity.UNCOMMON: 0.0,
    Rarity.RARE: 0.0,
    Rarity.EPIC: 0.10,
    Rarity.LEGENDARY: 0.25,
    Rarity.MYTHIC: 0.40,
    Rarity.ANCIENT: 0.55,
    Rarity.DIVINE: 0.75,
}

# How much each point of Luck skews weighted rolls toward higher rarities.
# Applied multiplicatively per rarity tier index (0=Common..7=Divine) in
# generator.roll_rarity, so Luck helps at the top end much more than the
# bottom, without needing to touch Common/Uncommon weights directly.
LUCK_SKEW_PER_POINT = 0.006
