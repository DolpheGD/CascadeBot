"""
The universe of rollable stats, which item types can roll which main stats,
and how fast each stat grows per item level.

STAT_KEYS must match attribute names on bot.database.models.player_model.Player
so combat can apply them uniformly whether the source is base stats or gear.

Substats can be FLAT (added directly) or PERCENT (a percentage of the
PLAYER'S OWN BASE stat, computed once and added as a flat bonus -- percent
substats never compound with other equipped items; see
bot/game/combat/factory.py for exactly how that's resolved). Only stats
where that distinction makes sense allow a percent roll -- crit_rate,
crit_damage, and recharge are already small percentages/flat numbers, so
they only ever roll flat.
"""

from __future__ import annotations

STAT_KEYS = [
    "attack",
    "defense",
    "elemental",
    "speed",
    "max_hp",
    "max_mana",
    "crit_rate",
    "crit_damage",
    "recharge",
]

# Which main stat(s) an item of a given ItemType can roll. Picked explicitly
# per ItemTemplate at authoring time (not random) -- this is just the legal
# menu for content authors / the admin test-gear generator.
MAIN_STAT_POOL_BY_ITEM_TYPE: dict[str, list[str]] = {
    "weapon": ["attack", "elemental"],
    "armor": ["defense", "max_hp", "speed", "recharge", "max_mana"],
    "accessory": ["defense", "max_hp", "speed", "recharge", "max_mana", "crit_rate", "crit_damage"],
    # Artifacts can now main-stat into HP or DEF too (Combat Overhaul), not
    # just offense/utility -- makes them viable on Sustain/tank builds.
    "artifact": ["speed", "recharge", "attack", "elemental", "crit_damage", "crit_rate", "max_hp", "defense"],
}

# Stats that may roll as a PERCENT-of-base substat, in addition to flat.
PERCENT_ELIGIBLE_STATS = {"attack", "defense", "elemental", "max_hp", "max_mana"}

# How much a template's main_stat_value grows per item_level, before the
# rarity multiplier. Different per stat because these live on very
# different scales -- attack/defense are single-to-low-double-digits at
# this scale, recharge and crit_rate/crit_damage are small percentages.
# recharge in particular is deliberately the slowest grower: it's a %-of-
# max-pool refund per basic attack now (see Combatant.gain_energy_and_mana),
# so a fast-growing recharge main stat would let high-item-level gear reach
# the ultimate in 1-2 turns -- exactly what the balancing pass calls out.
# Balancing pass: these (and the substat pools/RARITY_STAT_MULTIPLIER
# below) were cut roughly 8-10x from their original values, which let
# fully-leveled gear massively outscale the character wearing it.
# ----------------------------------------------------------------------
# THE MAIN-STAT LEVEL CURVE
#
# Levelling gear barely did anything. Measured, on a base-10 attack
# template:
#
#     common     level 1 -> 5    10.0 -> 10.4    (1.04x)
#     rare       level 1 -> 15   11.8 -> 13.5    (1.14x)
#     legendary  level 1 -> 25   14.5 -> 18.0    (1.24x)
#
# The additive term below is tiny next to the template's base value, so a
# freshly-dropped item was already ~80% of a fully-maxed one. Two things
# follow from that, and both were reported:
#
#   * gear is wildly strong for beginners -- your first Rare drop hands
#     you nearly everything that item will ever give
#   * every upgrade after it is invisible, so the whole material economy
#     is a grind with no payoff attached to it
#
# So the main stat is now MULTIPLIED by a level curve that starts below 1
# and ends well above it. Same template values, same rarity multipliers,
# redistributed along the level axis: you start weaker and finish far
# stronger, and each individual upgrade is a number you can see move.
#
# Anchored to an ABSOLUTE level rather than each rarity's own cap, on
# purpose. Anchoring to the cap would let a maxed Common ride the same
# multiplier as a maxed Divine, which would flatten rarity into "how many
# upgrades until I'm done". Anchoring absolutely means a Common tops out
# early on the curve and a Divine keeps climbing -- rarity buys you
# ACCESS to the steep part.
# ----------------------------------------------------------------------
# THE ONE FORMULA. Both the generator and the upgrade path call
# main_stat_for() below -- see the block above for why the curve exists,
# and this block for why it is a single function.
#
# It was not. `LootGenerator.roll_main_stat` applied the curve; the
# level-up path in loot/upgrades.py used its OWN arithmetic with a
# hardcoded growth of 1.0 and no curve at all. Two formulas for one
# number, and they disagreed enormously:
#
#     base-10 RARE attack item      generator   level_up()
#         level 1                       5.31       11.80
#         level 5                       6.69       16.52
#
# So an item was created weak, and the instant you upgraded it once it
# was recomputed on the other formula and JUMPED 2.44x -- then crawled,
# because level_up's growth was a flat +1.0 a level. That is exactly the
# reported "level 1 low, level 2 high, marginal after", and it survived
# the previous attempt at this because that pass only touched the
# generator, which is not the path an upgraded item goes through.
#
# LINEAR, as asked. The curve exponent is 1.0, so a level is worth the
# same amount of stat wherever you are on the climb: start very low, end
# high, no step anywhere.
# ----------------------------------------------------------------------
MAIN_STAT_LEVEL_1_MULTIPLIER = 0.35   # a level-1 item carries 35% of its base
MAIN_STAT_TOP_MULTIPLIER = 3.0        # ...and 3.0x at the anchor level
MAIN_STAT_ANCHOR_LEVEL = 30           # where TOP is reached (mythic's cap)
MAIN_STAT_CURVE_EXPONENT = 1.0        # 1.0 = strictly linear


def main_stat_level_multiplier(item_level: int) -> float:
    """How much of a main stat an item of this level carries."""
    span = max(1, MAIN_STAT_ANCHOR_LEVEL - 1)
    progress = max(0.0, (item_level - 1) / span) ** MAIN_STAT_CURVE_EXPONENT
    return MAIN_STAT_LEVEL_1_MULTIPLIER + (
        MAIN_STAT_TOP_MULTIPLIER - MAIN_STAT_LEVEL_1_MULTIPLIER
    ) * progress


# Per-stat ceilings. A stat's character now lives HERE rather than in a
# second additive growth term, because base * (linear curve) is a
# straight line and base * (linear curve) + (linear growth) is not -- the
# product of two level-dependent terms is quadratic, which put a visible
# bend in what was supposed to be a flat climb.
#
# recharge stays deliberately shallow: it is a %-of-max-pool refund per
# basic attack, so a fast-scaling recharge main stat lets high-level gear
# reach its ultimate in one or two turns.
MAIN_STAT_TOP_BY_STAT: dict[str, float] = {
    "attack": 3.0, "defense": 3.0, "elemental": 3.0,
    "max_hp": 3.4, "max_mana": 2.6,
    "speed": 2.2, "crit_rate": 2.2, "crit_damage": 2.6,
    "recharge": 1.8,
}


def main_stat_for(base_value: float, main_stat: str, item_level: int,
                  rarity_multiplier: float) -> float:
    """The main stat an item has. THE only definition -- both the loot
    generator and the upgrade path call this, so they cannot drift.

    Strictly linear in item_level: every level is worth the same amount
    of stat, from MAIN_STAT_LEVEL_1_MULTIPLIER at level 1 up to this
    stat's own ceiling at MAIN_STAT_ANCHOR_LEVEL.
    """
    top = MAIN_STAT_TOP_BY_STAT.get(main_stat, MAIN_STAT_TOP_MULTIPLIER)
    span = max(1, MAIN_STAT_ANCHOR_LEVEL - 1)
    progress = max(0.0, (item_level - 1) / span)
    multiplier = MAIN_STAT_LEVEL_1_MULTIPLIER + (
        top - MAIN_STAT_LEVEL_1_MULTIPLIER
    ) * progress
    return round(base_value * multiplier * rarity_multiplier, 2)


MAIN_STAT_GROWTH_PER_LEVEL: dict[str, float] = {
    "attack": 0.10,
    "defense": 0.10,
    "elemental": 0.10,
    "max_hp": 0.45,
    "max_mana": 0.22,
    "speed": 0.05,
    "crit_rate": 0.04,
    "crit_damage": 0.10,
    "recharge": 0.03,
}

# {stat: (per_level_min, per_level_max)} for a FLAT roll -- roll = level *
# uniform(min, max), then multiplied by the rarity's stat multiplier.
# Base ranges below are the original balancing-pass numbers (kept as
# documentation of that pass); SUBSTAT_VALUE_MULTIPLIER is applied on top
# per a later request to scale substats back up. Deliberately does NOT
# touch MAIN_STAT_GROWTH_PER_LEVEL or RARITY_STAT_MULTIPLIER above -- main
# stat scaling is explicitly out of scope for this pass, only substats.
SUBSTAT_VALUE_MULTIPLIER = 2.5  # +150%, i.e. roughly midway through the requested +100% to +200% range

_FLAT_SUBSTAT_POOL_BASE: dict[str, tuple[float, float]] = {
    "attack": (0.08, 0.18),
    "defense": (0.08, 0.18),
    "elemental": (0.08, 0.18),
    "speed": (0.04, 0.10),
    "max_hp": (0.35, 0.7),
    "max_mana": (0.15, 0.32),
    "crit_rate": (0.03, 0.08),
    "crit_damage": (0.08, 0.18),
    "recharge": (0.03, 0.09),
}

# {stat: (per_level_min, per_level_max)} for a PERCENT roll, in percentage
# points of the player's base stat. Deliberately small per level so a
# fully-percent-rolled build stays comparable to a flat-rolled one instead
# of dominating it. See SUBSTAT_VALUE_MULTIPLIER above.
_PERCENT_SUBSTAT_POOL_BASE: dict[str, tuple[float, float]] = {
    "attack": (0.04, 0.10),
    "defense": (0.04, 0.10),
    "elemental": (0.04, 0.10),
    "max_hp": (0.05, 0.12),
    "max_mana": (0.05, 0.12),
}

FLAT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    stat: (lo * SUBSTAT_VALUE_MULTIPLIER, hi * SUBSTAT_VALUE_MULTIPLIER)
    for stat, (lo, hi) in _FLAT_SUBSTAT_POOL_BASE.items()
}
PERCENT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    stat: (lo * SUBSTAT_VALUE_MULTIPLIER, hi * SUBSTAT_VALUE_MULTIPLIER)
    for stat, (lo, hi) in _PERCENT_SUBSTAT_POOL_BASE.items()
}


def roll_substat_value(stat: str, value_type: str, item_level: int, rarity_multiplier: float, rng) -> float:
    """Roll one substat's value for the given item level/rarity/type."""
    pool = PERCENT_SUBSTAT_POOL if value_type == "percent" else FLAT_SUBSTAT_POOL
    lo, hi = pool[stat]
    per_level = rng.uniform(lo, hi)
    value = per_level * max(item_level, 1) * rarity_multiplier
    return round(value, 2 if value_type == "percent" else 1)


def roll_substat_value_type(stat: str, rng) -> str:
    """Whether this substat rolls flat or percent, for stats where both are
    possible. Stats outside PERCENT_ELIGIBLE_STATS always roll flat."""
    if stat in PERCENT_ELIGIBLE_STATS and rng.random() < 0.5:
        return "percent"
    return "flat"
