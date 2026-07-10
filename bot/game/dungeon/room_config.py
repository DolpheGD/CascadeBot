"""
Tuning knobs for which room types can appear where in a run.

A dungeon is split into three "stages" by floor position (excluding the
forced START, CAMPFIRE-before-boss, and BOSS floors, which are never
randomized). Weights control the *likelihood* of a room type; MAX_PER_RUN
caps how many times a type can appear at all, so e.g. Merchant or Secret
stay special instead of showing up on every floor.
"""

from __future__ import annotations

from bot.database.models.enums import RoomType

# Room types that are placed by explicit rule, never rolled from weights.
FIXED_ROOM_TYPES = {RoomType.START, RoomType.CAMPFIRE, RoomType.BOSS}

ROOM_WEIGHTS_BY_STAGE: dict[str, dict[RoomType, float]] = {
    # First third: ease the player in, no elites yet.
    "early": {
        RoomType.COMBAT: 55,
        RoomType.TREASURE: 15,
        RoomType.STORY: 10,
        RoomType.MERCHANT: 8,
        RoomType.TRAP: 7,
        RoomType.SHRINE: 5,
    },
    # Middle third: elites and puzzles start appearing.
    "mid": {
        RoomType.COMBAT: 38,
        RoomType.ELITE: 15,
        RoomType.TREASURE: 12,
        RoomType.MERCHANT: 8,
        RoomType.STORY: 8,
        RoomType.TRAP: 7,
        RoomType.SHRINE: 6,
        RoomType.PUZZLE: 6,
    },
    # Final third before the pre-boss rest floor: hardest mix, secrets possible.
    "late": {
        RoomType.COMBAT: 32,
        RoomType.ELITE: 22,
        RoomType.TREASURE: 10,
        RoomType.MERCHANT: 6,
        RoomType.STORY: 5,
        RoomType.TRAP: 6,
        RoomType.SHRINE: 4,
        RoomType.PUZZLE: 4,
        RoomType.SECRET: 3,
    },
}

# Hard cap on how many nodes of a given type may exist in one generated
# dungeon (regardless of how generous the weights are). Absent = uncapped.
MAX_PER_RUN: dict[RoomType, int] = {
    RoomType.MERCHANT: 2,
    RoomType.SHRINE: 2,
    RoomType.PUZZLE: 2,
    RoomType.SECRET: 1,
}

# Elites are not allowed on the very first randomized floor (floor index 1) --
# it's too early to hit a hard fight right out of the start node.
ELITE_MIN_FLOOR_INDEX = 2

# Width (node count) of the forced rest floor placed right before the boss.
REST_FLOOR_WIDTH = 2

# How many boss fights a single expedition has, end to end -- picked once
# at expedition start. Weighted toward shorter runs so a typical run stays
# quick, with longer 3-4 boss runs as a rarer, bigger commitment for bigger
# cumulative rewards (each boss kill pays out the BOSS reward multiplier --
# see combat_service.ROOM_TYPE_REWARD_MULTIPLIER).
NUM_BOSSES_WEIGHTS: dict[int, float] = {1: 55.0, 2: 30.0, 3: 12.0, 4: 3.0}

# Random floors-per-segment range (a "segment" = the floors leading up to
# and including one boss fight, not counting the shared entry floor). Kept
# the same regardless of how many bosses the run has, so total length
# scales roughly linearly with num_bosses rather than each segment
# shrinking to compensate.
SEGMENT_FLOOR_RANGE = (5, 8)


def roll_num_bosses(rng) -> int:
    counts = list(NUM_BOSSES_WEIGHTS.keys())
    weights = list(NUM_BOSSES_WEIGHTS.values())
    return rng.choices(counts, weights=weights, k=1)[0]
