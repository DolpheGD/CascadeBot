"""
Core combat math, kept separate from the battle loop so it's easy to test
and retune in isolation.

Percentage mitigation: defense reduces damage by defense / (defense + K).
This gives diminishing returns rather than a hard cap -- 100 defense halves
damage, 300 defense cuts it to a quarter, but defense can never fully
negate an attack. Chosen over flat subtraction so gear scales meaningfully
at high item levels instead of stats becoming irrelevant past a threshold.
"""

from __future__ import annotations

import random

MITIGATION_K = 100


def mitigate(raw_damage: float, defense: float) -> float:
    if raw_damage <= 0:
        return 0.0
    reduction = defense / (defense + MITIGATION_K)
    return raw_damage * (1 - reduction)


def roll_percent(chance: float, rng: random.Random) -> bool:
    """`chance` is a 0-100 percentage."""
    return rng.uniform(0, 100) < chance


def crit_multiplier(crit_damage_percent: float) -> float:
    return crit_damage_percent / 100
