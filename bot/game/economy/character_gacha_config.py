"""
Tuning for the character gacha -- the ONLY way to acquire characters (per
the Combat Overhaul spec: pulling was overhauled to be characters-only,
gear no longer comes from this banner). Odds are keyed by star rating
rather than item Rarity since characters don't have a Rarity of their own.

----------------------------------------------------------------------
Pity
----------------------------------------------------------------------
Raw weighted rolls alone mean a genuinely unlucky player can pull 100+
times and never see a 5-star, which is the single most common way a
gacha loses someone. Two independent counters (persisted on Player, so
they survive across sessions and across single/multi pulls alike) fix
that:

  * FIVE_STAR_HARD_PITY -- a 5-star is GUARANTEED on this pull number.
    The counter resets to 0 the moment any 5-star is pulled, whether it
    came from the guarantee or from a normal roll.
  * FIVE_STAR_SOFT_PITY_START -- from this pull onward, the 5-star rate
    climbs by FIVE_STAR_SOFT_PITY_STEP per additional pull, so the
    guarantee is usually pre-empted by an "earned" 5-star a few pulls
    early rather than always landing on the exact same number. This is
    what stops every 5-star in the game feeling handed out by a counter.
  * FOUR_STAR_PITY -- a 4-star-or-better is guaranteed every N pulls,
    reset by pulling ANY 4-star or 5-star (a 5-star satisfies the
    4-star guarantee -- it's strictly better, and not resetting it would
    hand out a free extra 4-star on the very next pull).

Both counters increment on every single pull, including each individual
roll inside a 10-pull, so a multi-pull is exactly ten singles for pity
purposes and there's no advantage to splitting them up.
"""

from __future__ import annotations

import random

# Relative odds by star rating -- classic gacha shape: 3-star is the
# baseline you'll see constantly, 5-star is the aspirational pull. These
# are the BASE rates, before any soft-pity ramp is applied.
STAR_WEIGHTS: dict[int, float] = {
    3: 75.0,
    4: 21.0,
    5: 4.0,
}

SINGLE_PULL_COST_SHARDS = 120
MULTI_PULL_COUNT = 10
# Exactly 10x the single cost -- no bulk discount.
#
# The discount was pushing every player toward the 10x button for a
# reason that had nothing to do with what they wanted: with pity
# counters running continuously across both (see the PITY block
# below), a 10x is already the strictly better way to bank progress,
# and paying less for it as well made the single pull pointless.
# Same price per pull means 10x is a convenience, not a tax on
# pulling one at a time.
MULTI_PULL_COST_SHARDS = SINGLE_PULL_COST_SHARDS * MULTI_PULL_COUNT

# ---------------------------------------------------------------------
# Pity tuning. At 150 shards a pull, a 50-pull hard ceiling is 7,500
# shards -- a real but reachable target for a committed player, which is
# the point: the guarantee should be something you can plan toward, not
# a theoretical backstop you rarely touch.
# ---------------------------------------------------------------------
FIVE_STAR_HARD_PITY = 50
FIVE_STAR_SOFT_PITY_START = 30
# Percentage points added to the 5-star chance per pull past the soft
# pity threshold. Over pulls 30..49 this ramps the effective rate from
# the ~4% base up past 100%, so in practice most 5-stars land in the
# high 30s / low 40s rather than exactly on 50.
FIVE_STAR_SOFT_PITY_STEP = 5.0

FOUR_STAR_PITY = 10


def five_star_chance_percent(pulls_since_five_star: int) -> float:
    """The 5-star chance (0-100) for a pull that is
    `pulls_since_five_star` pulls deep into the current pity cycle --
    i.e. the counter BEFORE this pull is counted. Flat at the base rate
    until soft pity, then ramps linearly. Callers should check hard pity
    separately; this can exceed 100 and is clamped by the caller."""
    base = STAR_WEIGHTS[5] / sum(STAR_WEIGHTS.values()) * 100
    pulls_into_soft = (pulls_since_five_star + 1) - FIVE_STAR_SOFT_PITY_START
    if pulls_into_soft <= 0:
        return base
    return min(100.0, base + pulls_into_soft * FIVE_STAR_SOFT_PITY_STEP)


def roll_star_rating(
    rng: random.Random,
    pulls_since_five_star: int = 0,
    pulls_since_four_star: int = 0,
    hard_pity: int | None = None,
) -> int:
    """Rolls one pull's star rating, honouring both pity counters. The
    counters passed in are the state BEFORE this pull; the caller is
    responsible for updating them from the result (see
    character_gacha_service._pull_one).

    Resolution order is deliberate: hard 5-star pity wins outright, then
    the soft-pity-boosted 5-star roll, then the 4-star guarantee, and
    only then the ordinary weighted 3/4 split. A 5-star must be able to
    pre-empt the 4-star guarantee, or the guaranteed-4-star pull would
    be the one pull where a 5-star is impossible."""
    # `hard_pity` is per-player: the Research Lab can shorten it (see
    # character_gacha_service._pity_threshold). Defaults to the global
    # value for callers that don't have a player in hand.
    if pulls_since_five_star + 1 >= (hard_pity or FIVE_STAR_HARD_PITY):
        return 5

    if rng.random() * 100 < five_star_chance_percent(pulls_since_five_star):
        return 5

    if pulls_since_four_star + 1 >= FOUR_STAR_PITY:
        return 4

    # Ordinary roll with the 5-star share removed -- it already had its
    # chance above, and rolling it again here would double-count it.
    stars = [3, 4]
    weights = [STAR_WEIGHTS[3], STAR_WEIGHTS[4]]
    return rng.choices(stars, weights=weights, k=1)[0]
