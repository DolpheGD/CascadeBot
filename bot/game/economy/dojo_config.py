"""
Tuning for the Dojo.

THE ONE PROBLEM THIS FILE EXISTS TO SOLVE. Player-authored content that
pays rewards is the oldest exploit in the genre: build the weakest
encounter the rules allow, clear it in one turn, repeat forever. Every
number below is either a bound on that or a bound on what an author can
inflict on somebody else.

WHAT THE DOJO IS FOR, per the design brief: building and sharing fights,
with a small amount of XP so that clearing something is not literally
worthless. It is explicitly NOT an XP source anybody should want to
grind, and the numbers are set so that trying is worse than playing the
game normally.

TWO INDEPENDENT LIMITS, because either alone leaks:

  1. A DAILY CAP on rewarded clears. Beyond it you can play as much as
     you like and are paid nothing.

  2. XP SCALED BY THE ENEMY BUDGET. Within a daily cap, the efficient
     play is always the EASIEST challenge that still pays -- a cap alone
     makes "one level-1 enemy" the correct build. Scaling the payout by
     what the challenge actually fields removes that: a trivial encounter
     pays trivially, so there is nothing to optimise toward.

Even fully exploited, a day of dojo clears is worth less XP than a single
expedition. That is the intended relationship and the check asserts it.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# What an author may build
# ----------------------------------------------------------------------

# Enemy stacks per challenge, and copies per stack. Three stacks of four
# is twelve bodies, which is already well past what any authored fight in
# the game fields -- the cap is here to stop a challenge that takes ten
# minutes to resolve, not to stop a hard one.
MAX_ENEMY_STACKS = 3
MAX_COUNT_PER_STACK = 4
MAX_TOTAL_ENEMIES = 6

# Level bounds. The floor is 1 rather than 0 because a level-0 enemy has
# no stats to speak of and would be a way of publishing an empty fight.
MIN_LEVEL = 1
MAX_LEVEL = 100

# Player-authored text.
MAX_NAME_LENGTH = 48
MAX_DESCRIPTION_LENGTH = 200

# How many challenges one author may keep. Not a performance limit -- it
# is the anti-spam limit, since the browse list is the shared surface and
# one person publishing two hundred entries makes it useless for
# everybody else.
MAX_CHALLENGES_PER_AUTHOR = 10

# ----------------------------------------------------------------------
# Rewards
# ----------------------------------------------------------------------

# Rewarded clears per day, across ALL dojo challenges. Beyond this,
# clearing still works and still records -- it just pays nothing.
REWARDED_CLEARS_PER_DAY = 5

# XP per unit of enemy budget, where budget is (total enemy levels).
# Deliberately small: at the daily cap, against the largest legal
# challenge, this is a fraction of one expedition.
XP_PER_BUDGET_POINT = 1.2

# Nobody clears anything for zero, and nobody should clear the maximum
# for a meaningful amount either.
MIN_XP_PER_CLEAR = 5
MAX_XP_PER_CLEAR = 400

# A challenge you have never beaten pays this multiple on the first
# clear. It is the one nod to "new content is worth more" and it cannot
# be farmed, because there is exactly one first clear per challenge.
FIRST_CLEAR_MULTIPLIER = 2.0


def enemy_budget(enemies: list[dict], level: int) -> int:
    """Total levels fielded -- the size of the fight, in one number.

    Deliberately crude. It only has to ORDER challenges by how much they
    ask of the player, and anything more precise (effective HP, ability
    strength) would be a second combat model to keep in step with the
    real one -- the same reasoning squad_power uses for matchmaking.
    """
    total = sum(int(stack.get("count", 1)) for stack in enemies)
    return max(0, total * max(0, int(level)))


def xp_for_clear(enemies: list[dict], level: int, first_clear: bool) -> int:
    """What one clear pays, before the daily cap is applied."""
    budget = enemy_budget(enemies, level)
    xp = budget * XP_PER_BUDGET_POINT
    if first_clear:
        xp *= FIRST_CLEAR_MULTIPLIER
    return int(max(MIN_XP_PER_CLEAR, min(MAX_XP_PER_CLEAR, round(xp))))


def max_daily_xp() -> int:
    """The most XP the dojo can pay one player in a day.

    Exists so the check can assert it against an expedition's payout
    rather than that relationship living only in a comment.
    """
    return MAX_XP_PER_CLEAR * REWARDED_CLEARS_PER_DAY
