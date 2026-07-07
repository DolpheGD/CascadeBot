"""
The universe of rollable stats, and how fast each one grows per item level.

STAT_KEYS must match attribute names on bot.database.models.player_model.Player
so combat can apply them uniformly whether the source is base stats or gear.

SUBSTAT_POOL entries define, per level, a (min, max) flat value range at
Common rarity/quality 100 -- the generator scales this by item_level and the
rarity multiplier from rarity_config.py.
"""

from __future__ import annotations

STAT_KEYS = [
    "attack",
    "defense",
    "magic",
    "speed",
    "luck",
    "max_hp",
    "crit_chance",
    "crit_damage",
    "dodge",
    "healing_bonus",
]

# Default main stat per slot, used by seed/authoring scripts as a sane
# starting point. ItemTemplate.main_stat is still authored explicitly per
# item (a "Battle Ring" could give attack instead of the ring default).
DEFAULT_MAIN_STAT_BY_SLOT: dict[str, str] = {
    "weapon": "attack",
    "helmet": "defense",
    "chest": "max_hp",
    "leggings": "defense",
    "boots": "speed",
    "ring": "crit_chance",
    "necklace": "magic",
}

# {stat: (per_level_min, per_level_max)} -- roll = level * uniform(min, max),
# then multiplied by the rarity's stat multiplier. Percent-based stats
# (crit_chance, dodge, etc.) intentionally grow slower than flat stats so
# they don't spiral out of control at high item levels.
SUBSTAT_POOL: dict[str, tuple[float, float]] = {
    "attack": (0.8, 1.6),
    "defense": (0.8, 1.6),
    "magic": (0.8, 1.6),
    "speed": (0.5, 1.0),
    "luck": (0.4, 0.8),
    "max_hp": (3.0, 6.0),
    "crit_chance": (0.15, 0.35),
    "crit_damage": (0.4, 0.9),
    "dodge": (0.15, 0.3),
    "healing_bonus": (0.2, 0.5),
}


def roll_substat_value(stat: str, item_level: int, rarity_multiplier: float, rng) -> float:
    """Roll one substat's value for the given item level/rarity."""
    lo, hi = SUBSTAT_POOL[stat]
    per_level = rng.uniform(lo, hi)
    value = per_level * max(item_level, 1) * rarity_multiplier
    return round(value, 1)
