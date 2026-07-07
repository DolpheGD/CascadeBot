"""
Gacha pulls use a distinct, more generous rarity table than natural dungeon
drops (bot/game/loot/rarity_config.py) -- no Commons, and a meaningfully
better floor at every tier. This is what makes spending Shards feel worth
it compared to just running expeditions.
"""

from __future__ import annotations

import random

from bot.database.models.enums import Rarity

GACHA_RARITY_WEIGHTS: dict[Rarity, float] = {
    Rarity.UNCOMMON: 30.0,
    Rarity.RARE: 35.0,
    Rarity.EPIC: 20.0,
    Rarity.LEGENDARY: 10.0,
    Rarity.MYTHIC: 3.5,
    Rarity.ANCIENT: 1.2,
    Rarity.DIVINE: 0.3,
}

SINGLE_PULL_COST_SHARDS = 100
MULTI_PULL_COUNT = 10
MULTI_PULL_COST_SHARDS = 900  # 10% discount vs 10x single pulls


def roll_gacha_rarity(rng: random.Random) -> Rarity:
    rarities = list(GACHA_RARITY_WEIGHTS.keys())
    weights = list(GACHA_RARITY_WEIGHTS.values())
    return rng.choices(rarities, weights=weights, k=1)[0]
