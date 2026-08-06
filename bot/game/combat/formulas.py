"""
Core combat math, kept separate from the battle loop so it's easy to test
and retune in isolation.

Percentage mitigation: defense reduces damage by defense / (defense + K).
This gives diminishing returns rather than a hard cap 
"""

from __future__ import annotations

import random

# 45, down from 70.
#
# Reduction is defense/(defense+K), so a LOWER K makes defense -- and
# every debuff that strips it -- matter more. At K=70 a 30% DEF shred
# bought about 12% more damage, which is why "DEF shred" measured at 46%
# of the crit-stack comp and nobody built it. At K=45 the same shred is
# worth roughly twice that.
#
# This also makes enemy defense meaningful, which is the point: if
# mitigation is negligible then the only thing worth buffing is your own
# damage, and that is exactly the one-strategy problem.
MITIGATION_K = 45


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
