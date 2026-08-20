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

# COMBAT DENSITY WAS TUNED FOR A RUN A THIRD THE LENGTH.
#
# These weights date from when a segment was 8-11 floors and the roles
# benchmark walked exactly 9. A real route is now ~45 rooms, and at the
# old weights that meant 24 fights per run against the 7 the balance had
# ever been measured on.
#
# Fights compound multiplicatively, not additively: at a 10% chance of
# losing any given fight, 7 fights is a 52% clear and 24 fights is an 8%
# one. Measured, Abyssnia went from a 25% clear rate to 1% purely from
# length -- and raising campfire healing from 50% to 100% moved it by
# nothing at all, which is what told us recovery was never the binding
# constraint.
#
# So combat weight comes down and the freed weight goes to the content
# that was just built -- relic events, treasure, story -- which is also
# the answer to "longer maps" that does not simply mean "more of the
# same fight".
ROOM_WEIGHTS_BY_STAGE: dict[str, dict[RoomType, float]] = {
    # First third: ease the player in, no elites yet.
    "early": {
        RoomType.COMBAT: 34,
        RoomType.TREASURE: 22,
        RoomType.STORY: 16,
        RoomType.MERCHANT: 8,
        RoomType.TRAP: 7,
        RoomType.SHRINE: 5,
    },
    # Middle third: elites and puzzles start appearing.
    "mid": {
        RoomType.COMBAT: 24,
        RoomType.ELITE: 11,
        RoomType.TREASURE: 18,
        RoomType.MERCHANT: 8,
        RoomType.STORY: 14,
        RoomType.TRAP: 7,
        RoomType.SHRINE: 6,
        RoomType.PUZZLE: 6,
        # Relic events -- a relic priced in HP rather than gold. Six of
        # them, resolved by the ordinary encounter interpreter (see
        # encounter_config/relic_event.py). Weighted low and capped per
        # run because their whole value is being unusual.
        #
        # These shipped at weight 0 for one pass, deliberately: the room
        # type existed before dungeon_service could resolve it, and an
        # unhandled room falls through to "Something happens." and marks
        # itself complete. A dead tile on every route is worse than a
        # feature that arrives a pass later.
        RoomType.RELIC_EVENT: 5,
    },
    # Final third before the pre-boss rest floor: hardest mix, secrets possible.
    "late": {
        RoomType.COMBAT: 20,
        RoomType.ELITE: 15,
        RoomType.TREASURE: 16,
        RoomType.MERCHANT: 6,
        RoomType.STORY: 10,
        RoomType.TRAP: 6,
        RoomType.SHRINE: 4,
        RoomType.PUZZLE: 4,
        RoomType.SECRET: 3,
        RoomType.RELIC_EVENT: 6,
    },
}

# Hard cap on how many nodes of a given type may exist in one generated
# dungeon (regardless of how generous the weights are). Absent = uncapped.
MAX_PER_RUN: dict[RoomType, int] = {
    RoomType.MERCHANT: 2,
    RoomType.SHRINE: 2,
    RoomType.PUZZLE: 2,
    RoomType.SECRET: 1,
    # See relic_event_config.MAX_RELIC_EVENTS_PER_RUN -- the cap lives
    # there as the design number and is mirrored here as the generator's
    # enforcement point. tools/check_relic_events.py asserts the two
    # agree, because a cap defined twice is a cap that will disagree.
    RoomType.RELIC_EVENT: 3,
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
# FEWER BOSSES, LONGER ROADS BETWEEN THEM.
#
# Was {2: 45, 3: 35, 4: 20} regular bosses -- plus the guaranteed final
# one, so 3-5 boss fights per run. Now 2-3 regular plus the final, i.e.
# 3-4 total, and SEGMENT_FLOOR_RANGE below grew to compensate so a run is
# no shorter overall.
#
# The reason is the map rewrite. A boss node is a funnel: every route
# converges on it, so divergence resets to zero at every boss. With five
# of them, no branching decision could survive more than ~8 floors, which
# put a hard ceiling on how much planning ahead was ever worth doing.
# Measured after the change: run-wide lock-out rose from 18% to the high
# twenties, with per-segment lock-out unchanged at ~75% -- the same
# branching, over a longer stretch where it compounds.
NUM_REGULAR_BOSSES_WEIGHTS: dict[int, float] = {2: 55.0, 3: 45.0}

# Random floors-per-segment range (a "segment" = the floors leading up to
# and including one boss fight, not counting the shared entry floor). This
# range yields 6-9 real rooms before hitting each boss (segment length
# minus the start/campfire/boss floors that aren't randomized), and is
# kept the same regardless of how many bosses the run has, so total length
# scales roughly linearly with the boss count rather than each segment
# shrinking to compensate.
# Grown from (8, 11) alongside the boss-count reduction above. Total run
# length is deliberately held roughly constant -- 3 bosses x 14 floors is
# the same journey as 5 x 9, spent on route decisions instead of on boss
# intros. Balance implication: the squad now fights fewer bosses but more
# ordinary rooms between rests, so per-run attrition is what moved, and
# that is what tools/bench_roles.py was re-run to confirm.
SEGMENT_FLOOR_RANGE = (12, 16)

# A segment at least this long gets a SECOND campfire floor, near its
# midpoint, on top of the guaranteed one before the boss. See the block
# in generator._assign_room_types for the measurement that motivated it.
MID_REST_MIN_SEGMENT_FLOORS = 12


def roll_num_regular_bosses(rng) -> int:
    counts = list(NUM_REGULAR_BOSSES_WEIGHTS.keys())
    weights = list(NUM_REGULAR_BOSSES_WEIGHTS.values())
    return rng.choices(counts, weights=weights, k=1)[0]
