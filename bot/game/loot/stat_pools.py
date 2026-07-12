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
FLAT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
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
# of dominating it.
PERCENT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    "attack": (0.04, 0.10),
    "defense": (0.04, 0.10),
    "elemental": (0.04, 0.10),
    "max_hp": (0.05, 0.12),
    "max_mana": (0.05, 0.12),
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
