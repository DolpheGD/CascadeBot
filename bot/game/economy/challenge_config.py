"""
Tuning for async squad challenges.

You fight a SNAPSHOT of another player's squad, controlled by the same AI
that runs every other enemy. They are not playing; nothing happens on
their side; there is no timing, no queue and no notification to answer.
It is a single-player fight whose enemies happen to have been assembled
by somebody else.
"""

from __future__ import annotations

# How many challenges pay out per day. Beyond this you may still fight --
# the fights are the fun part -- but the rewards stop, which is the
# cheapest way to stop this becoming the most efficient farm in the game
# while leaving it available to somebody who just enjoys it.
REWARDED_CHALLENGES_PER_DAY = 5

# Matchmaking band, as a fraction of the challenger's own power. Wide
# enough that a small player base still finds opponents, narrow enough
# that a level-8 squad is not shown a level-70 one.
POWER_BAND = 0.45

# How many opponents to offer at once.
OPPONENT_CHOICES = 3

# Rewards scale with the opponent's power relative to yours, so beating
# somebody stronger is worth more and farming somebody weaker is worth
# very little. Multiplier is clamped to this range.
UNDERDOG_BONUS_MAX = 2.0
OVERDOG_PENALTY_MIN = 0.25

# Base payout for a win, before the power multiplier.
#
# CUT TO ROUGHLY A THIRD when weekly cycles arrived, and the arithmetic
# matters more than the ratio. The old numbers were sized to be the mode's
# WHOLE reward; most of that value now lives in the cycle claim below, and
# leaving both at full size would have roughly tripled what challenges pay
# -- the daily cap exists precisely so this does not become the most
# efficient farm in the game, and doubling the payout would have walked
# straight past it.
#
# It is deliberately not cut to nothing. A fight that pays zero today and
# promises something on Sunday is a fight people stop taking on Tuesday;
# the immediate payout is what makes the fight worth pressing, and the
# cycle is what makes the WEEK worth playing.
WIN_REWARD = {"gold": 1400, "shards": 15, "cores": 20, "evolution_fragments": 18}

# A loss still pays something. A mode that pays nothing when you lose is a
# mode people stop entering once they have lost twice, and the fights are
# the content.
LOSS_REWARD = {"gold": 300, "shards": 3}

# The defending squad fights at full health and gets no relics, cards
# beyond their own, or player input. It is deliberately NOT buffed: the
# attacker chose to be here and the defender did not, so the fight is
# tuned to be winnable rather than to be an even match.
DEFENDER_HP_PERCENT = 100


# ======================================================================
# CHALLENGE CYCLES
# ======================================================================
# Wins bank POINTS. Points accumulate across a cycle, and at the end of
# the cycle the player claims rewards from fixed milestones.
#
# WHY MILESTONES AND NOT A LEADERBOARD. A ranked ladder pays by finishing
# position, which needs a crowd to mean anything. On a server with four
# active players the same person wins every week, everyone else learns
# their result is decided before they start, and a new player can never
# place no matter how well they do. Milestones are a contract with the
# player instead of a contest with the room: hit the number, get the
# reward, and the same effort is worth the same thing whether the server
# has four people on it or four hundred.
#
# It also makes the mode honest on an empty server, which this one may
# well be on day one -- see find_opponents' widening band.
# ======================================================================

# Cycle length in days. Weekly.
#
# A DAILY cycle was the alternative and is worse here for a specific
# reason: at REWARDED_CHALLENGES_PER_DAY fights a day, one day is a
# maximum of five results, so the gap between a good day and a perfect
# one is a couple of fights and the milestones would have to sit almost
# on top of each other. A week is ~35 rewarded fights, which is enough
# spread for milestones to mean genuinely different amounts of play --
# and it means missing a day costs you some of a cycle instead of all of
# one.
CYCLE_LENGTH_DAYS = 7

# Points for a result, before the power multiplier that already scales
# gold. Beating somebody stronger is worth more here for the same reason
# it pays more there.
POINTS_PER_WIN = 10
POINTS_PER_LOSS = 2

# Points only accrue on fights that are within the daily rewarded cap.
# Otherwise the cap stops being a cap: a player could fight fifty times a
# day for no gold and still bank a cycle's worth of points, which is the
# same farm wearing a different hat.
#
# The milestones below are sized against the cap, so this is not a detail
# -- it is the assumption they rest on.
#
# Reference points, at 10 per win and 5 rewarded fights a day:
#     one perfect day        =  50
#     a perfect week         = 350
#     winning half your fights, most days = ~150-200
MILESTONES = [
    # (points, label, rewards)
    (60,  "Contender",  {"gold": 12000, "shards": 120, "cores": 150}),
    (150, "Challenger", {"gold": 30000, "shards": 300, "cores": 380,
                         "evolution_fragments": 260}),
    (260, "Rival",      {"gold": 62000, "shards": 620, "cores": 780,
                         "evolution_fragments": 560}),
    (350, "Undefeated", {"gold": 110000, "shards": 1100, "cores": 1400,
                         "evolution_fragments": 1000}),
]

# Milestones are CUMULATIVE: reaching Rival pays Contender and Challenger
# as well. Claiming is therefore one action that settles the whole cycle,
# rather than four buttons the player has to remember to press -- and a
# player who forgets to claim until Thursday has lost nothing, because
# the previous cycle's total is banked when the new one starts.
CUMULATIVE_MILESTONES = True
