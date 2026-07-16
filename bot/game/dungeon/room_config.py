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

# How many REGULAR boss fights a single expedition has before its
# guaranteed FINAL boss -- picked once at expedition start. The run always
# ends with one extra, tougher final-boss segment on top of this count
# (see DungeonGenerator.generate() and enemy_catalog.get_boss_encounter's
# region_roles "final" vs "regular" split) -- so total boss fights per run
# is this value + 1, i.e. 3-5 end to end. Weighted toward the shorter end
# so a typical run stays reasonable, with a 4-regular-boss (5 total)
# marathon as a rarer, bigger commitment for bigger cumulative rewards
# (each boss kill pays out the BOSS reward multiplier -- see
# combat_service.ROOM_TYPE_REWARD_MULTIPLIER).
NUM_REGULAR_BOSSES_WEIGHTS: dict[int, float] = {2: 45.0, 3: 35.0, 4: 20.0}

# Random floors-per-segment range (a "segment" = the floors leading up to
# and including one boss fight, not counting the shared entry floor). This
# range yields 6-9 real rooms before hitting each boss (segment length
# minus the start/campfire/boss floors that aren't randomized), and is
# kept the same regardless of how many bosses the run has, so total length
# scales roughly linearly with the boss count rather than each segment
# shrinking to compensate.
SEGMENT_FLOOR_RANGE = (8, 11)


def roll_num_regular_bosses(rng) -> int:
    counts = list(NUM_REGULAR_BOSSES_WEIGHTS.keys())
    weights = list(NUM_REGULAR_BOSSES_WEIGHTS.values())
    return rng.choices(counts, weights=weights, k=1)[0]
