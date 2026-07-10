"""
Tuning for the character gacha -- the ONLY way to acquire characters (per
the Combat Overhaul spec: pulling was overhauled to be characters-only,
gear no longer comes from this banner). Odds are keyed by star rating
rather than item Rarity since characters don't have a Rarity of their own.
"""

from __future__ import annotations

import random

# Relative odds by star rating -- classic gacha shape: 3-star is the
# baseline you'll see constantly, 5-star is the aspirational pull.
STAR_WEIGHTS: dict[int, float] = {
    3: 75.0,
    4: 21.0,
    5: 4.0,
}

SINGLE_PULL_COST_SHARDS = 150
MULTI_PULL_COUNT = 10
MULTI_PULL_COST_SHARDS = 1350  # 10% discount vs 10x single pulls


def roll_star_rating(rng: random.Random) -> int:
    stars = list(STAR_WEIGHTS.keys())
    weights = list(STAR_WEIGHTS.values())
    return rng.choices(stars, weights=weights, k=1)[0]
