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
    "artifact": ["speed", "recharge", "attack", "elemental", "crit_damage", "crit_rate"],
    "scroll": ["attack", "elemental", "crit_damage", "max_hp"],
}

# Stats that may roll as a PERCENT-of-base substat, in addition to flat.
PERCENT_ELIGIBLE_STATS = {"attack", "defense", "elemental", "max_hp", "max_mana"}

# {stat: (per_level_min, per_level_max)} for a FLAT roll -- roll = level *
# uniform(min, max), then multiplied by the rarity's stat multiplier.
FLAT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    "attack": (0.8, 1.6),
    "defense": (0.8, 1.6),
    "elemental": (0.8, 1.6),
    "speed": (0.5, 1.0),
    "max_hp": (3.0, 6.0),
    "max_mana": (1.5, 3.0),
    "crit_rate": (0.15, 0.35),
    "crit_damage": (0.4, 0.9),
    "recharge": (0.1, 0.3),
}

# {stat: (per_level_min, per_level_max)} for a PERCENT roll, in percentage
# points of the player's base stat. Deliberately small per level so a
# fully-percent-rolled build stays comparable to a flat-rolled one instead
# of dominating it.
PERCENT_SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    "attack": (0.15, 0.35),
    "defense": (0.15, 0.35),
    "elemental": (0.15, 0.35),
    "max_hp": (0.2, 0.45),
    "max_mana": (0.2, 0.45),
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
