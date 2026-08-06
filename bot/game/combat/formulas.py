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
#
# It is now the value of K AT REFERENCE_LEVEL, not a constant -- see
# below.
MITIGATION_K = 45

# ----------------------------------------------------------------------
# WHY K SCALES, AND WHY REDUCTION IS CAPPED
# ----------------------------------------------------------------------
# A CONSTANT K makes defence get better and better as the game goes on,
# because reduction = DEF/(DEF+K) approaches 1 while K stays put. In
# practice, with a squad geared for each region:
#
#     Glacier 15   DEF  70  ->  61% reduction  -> takes 39% of raw
#     Wastelands   DEF 150  ->  77%            -> takes 23%
#     Hotlands     DEF 260  ->  85%            -> takes 15%
#     Voidcrest    DEF 400  ->  90%            -> takes 10%
#     Abyssnia     DEF 560  ->  93%            -> takes  7%
#
# Enemy attack over the same span grows about 4x, but incoming damage is
# divided by 5.3x -- so the LATE game is strictly gentler than the early
# game. That is exactly the report: Abyssnia enemies doing 20 damage to
# a 500 HP character, while Glacier 15 feels right.
#
# Two changes, together:
#
#   1. K SCALES WITH THE ATTACKER'S LEVEL, anchored so that a level-17
#      attacker (Glacier 15's depth) sees exactly the old K=45. Glacier
#      is the region the balance is judged against, so it is deliberately
#      left untouched to the point.
#
#   2. REDUCTION IS CAPPED. Scaling K alone still drifts, because gear
#      DEF climbs faster than level does. The cap is what guarantees the
#      floor: nothing can ever take less than (1 - MAX_REDUCTION) of a
#      hit, at any level, with any gear.
#
# DEF still does real work -- going from 0 to soft-capped is a 3.3x
# reduction in damage taken, and DEF shred still moves the number
# because it moves you back down the curve. What it can no longer do is
# quietly make the endgame safer than the tutorial.
REFERENCE_LEVEL = 17
MAX_REDUCTION = 0.70


def mitigation_k(attacker_level: int) -> float:
    """K for an attacker of this level. Linear in level and anchored at
    REFERENCE_LEVEL so Glacier 15's numbers are unchanged."""
    level = max(1, int(attacker_level or REFERENCE_LEVEL))
    return MITIGATION_K * level / REFERENCE_LEVEL


def mitigate(raw_damage: float, defense: float, attacker_level: int | None = None) -> float:
    if raw_damage <= 0:
        return 0.0
    k = mitigation_k(attacker_level if attacker_level else REFERENCE_LEVEL)
    reduction = min(MAX_REDUCTION, defense / (defense + k))
    return raw_damage * (1 - reduction)


def roll_percent(chance: float, rng: random.Random) -> bool:
    """`chance` is a 0-100 percentage."""
    return rng.uniform(0, 100) < chance


def crit_multiplier(crit_damage_percent: float) -> float:
    return crit_damage_percent / 100
