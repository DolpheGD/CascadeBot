"""
Pure config for the mailbox: no DB template table needed (there's only ever
one mailbox per player), so this is code-tunable data, same pattern as
hq_config.HQ_LEVEL_CONFIG.

The wait window between packages is fixed regardless of level -- upgrading
the mailbox makes packages better, not faster.
"""

from __future__ import annotations

import datetime as dt
import random

# Every package arrives 30min-1hr after the last one was collected (or
# after the mailbox was first created), no matter the mailbox's level.
PACKAGE_MIN_MINUTES = 15
PACKAGE_MAX_MINUTES = 30

MAX_MAILBOX_LEVEL = 5

# Cost to go from level N to N+1 -- e.g. MAILBOX_UPGRADE_COST[1] is the
# price of upgrading a level-1 mailbox to level 2. No entry for
# MAX_MAILBOX_LEVEL since there's nowhere further to go.
MAILBOX_UPGRADE_COST: dict[int, dict[str, int]] = {
    1: {"gold": 300, "wood": 40},
    2: {"gold": 900, "wood": 80, "stone": 80},
    3: {"gold": 2500, "stone": 150, "metal": 60},
    4: {"gold": 6000, "metal": 150, "crystal": 40},
}

# Reward table per level: currency -> (min, max, chance). `chance` is the
# probability that currency rolls into the package at all (basic supplies
# like gold/wood/stone are near-guaranteed; rarer materials/shards are a
# bonus chance that opens up and improves at higher levels).
MAILBOX_REWARD_TABLE: dict[int, dict[str, tuple[int, int, float]]] = {
    1: {
        "gold": (20, 50, 1.0),
        "wood": (5, 15, 0.9),
        "stone": (5, 15, 0.9),
        "shards": (1, 3, 1.0),
    },
    2: {
        "gold": (40, 90, 1.0),
        "wood": (10, 25, 0.95),
        "stone": (10, 25, 0.95),
        "metal": (1, 5, 0.7),
        "shards": (2, 4, 1.0),
    
    },
    3: {
        "gold": (70, 150, 1.0),
        "wood": (15, 35, 1.0),
        "stone": (15, 35, 1.0),
        "metal": (5, 15, 0.9),
        "crystal": (1, 5, 0.7),
        "shards": (3, 5, 1.0),
    },
    4: {
        "gold": (120, 250, 1.0),
        "wood": (20, 45, 1.0),
        "stone": (20, 45, 1.0),
        "metal": (10, 25, 1.0),
        "crystal": (2, 6, 1.0),
        "shards": (4, 6, 1.0),
    },
    5: {
        "gold": (200, 400, 1.0),
        "wood": (30, 60, 1.0),
        "stone": (30, 60, 1.0),
        "metal": (15, 35, 1.0),
        "crystal": (3, 10, 1.0),
        "shards": (5, 7, 1.0),
    },
}


def upgrade_cost(level: int) -> dict[str, int] | None:
    return MAILBOX_UPGRADE_COST.get(level)


def is_max_level(level: int) -> bool:
    return level >= MAX_MAILBOX_LEVEL


def roll_package(level: int, rng: random.Random | None = None) -> dict[str, int]:
    """Rolls one package's worth of currency for a mailbox at `level`.
    Returns {currency: amount}, omitting any currency that rolled 0/failed
    its chance check."""
    rng = rng or random.Random()
    table = MAILBOX_REWARD_TABLE.get(level, MAILBOX_REWARD_TABLE[1])

    rewards: dict[str, int] = {}
    for currency, (low, high, chance) in table.items():
        if rng.random() > chance:
            continue
        amount = rng.randint(low, high)
        if amount > 0:
            rewards[currency] = amount
    return rewards


def roll_next_package_delay(rng: random.Random | None = None) -> dt.timedelta:
    rng = rng or random.Random()
    minutes = rng.uniform(PACKAGE_MIN_MINUTES, PACKAGE_MAX_MINUTES)
    return dt.timedelta(minutes=minutes)
