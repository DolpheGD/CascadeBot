"""
Tuning for the /vote command (top.gg voting rewards). Kept separate from
bot/services/vote_service.py so the curves can be retuned without touching
the claim/streak logic -- same split as daily_config.py and its service.

A strong recurring reward, but no longer the only one that matters. Top.gg
allows one vote per bot every 12 hours, so a committed player can claim
this twice a day; the numbers below assume that. GOLD and LOOTBOXES lead
the package now -- see the rebalance block further down for why shards
stopped leading it, and what the old numbers were actually doing to the
gacha.

    BALANCE NOTE. Every knob here is a plain module-level constant. If it
    lands wrong, VOTE_BASE_SHARDS, VOTE_BASE_GOLD and the two _PER_STREAK
    values are the ones to pull first; nothing outside this module needs
    to change.

Streak semantics (implemented in vote_service.claim_vote):
  * Every claimed vote increments vote_streak by 1 -- so it can advance
    twice a day, not once, unlike daily_streak.
  * The streak survives as long as the next vote is claimed within
    VOTE_STREAK_GRACE_HOURS of the last one, which is generous enough
    that voting once a day keeps it alive; it only resets if a player
    goes a full day and a half without voting.
  * VOTE_COOLDOWN_HOURS matches top.gg's own 12h vote cooldown. It is a
    second line of defence, not the primary one: top.gg's API only
    reports "voted within the last 12h" with no vote identity, so
    Player.last_vote_claimed_at is what actually stops one vote being
    redeemed twice.
"""

from __future__ import annotations

from bot.database.models.enums import MATERIAL_TIERS

# Top.gg's own vote cooldown. Claiming again inside this window is
# rejected outright (see vote_service.VoteOnCooldown).
VOTE_COOLDOWN_HOURS = 12
# ...but the streak survives up to this long between claims, so a player
# who votes once a day (rather than the maximum twice) keeps it.
VOTE_STREAK_GRACE_HOURS = 36

# ----------------------------------------------------------------------
# REBALANCED: SHARDS DOWN HARD, GOLD UP HARD
# ----------------------------------------------------------------------
# These numbers were set when they were written and never revisited, and
# the economy moved underneath them in both directions at once.
#
# SHARDS. A pull costs 120. At a capped streak a single vote paid 980
# shards -- eight pulls -- and top.gg allows two votes a day, so voting
# was SIXTEEN PULLS A DAY, or thirty-two on a top.gg weekend. Against
# that, nothing else in the game is a shard source worth using: the
# hardest raid in the game pays its best contributor 24 pulls once, and
# /daily pays three. Voting wasn't the strongest recurring reward, it was
# the only one that mattered, and a gacha where the gacha is free isn't
# doing anything.
#
# GOLD. The opposite problem. 1,540 gold a vote was generous when it was
# written and is now a rounding error -- a single expedition pays more,
# and gear upgrades at the top of the curve cost tens of thousands. The
# reward that was supposed to be the sweetener had quietly become the
# part players ignored.
#
# So the mix inverts. Voting is now a steady GOLD and LOOTBOX faucet with
# a modest shard drip on top: about 2-3 pulls a day for a committed
# voter, against sixteen. The lootbox progression below is untouched --
# an epic box rising to mythic every single vote is a genuinely strong
# reward and is now the actual reason to vote.
VOTE_BASE_SHARDS = 70
VOTE_SHARDS_PER_STREAK = 5
VOTE_STREAK_CAP = 20  # streak stops scaling any reward past this

# Bonus shards every N consecutive votes, on top of the scaled amount.
VOTE_SHARD_MILESTONE_INTERVAL = 5
VOTE_SHARD_MILESTONE_AMOUNT = 150

# Gold and reroll tokens. Gold is now the headline currency here -- see
# the block above.
VOTE_BASE_GOLD = 2_000
VOTE_GOLD_PER_STREAK = 300
VOTE_REROLL_TOKENS = 20

# Materials: two from a streak-appropriate tier, same tier groupings
# everything else in the game uses (enums.MATERIAL_TIERS). Reaches the
# top tier faster than /daily does -- 15 votes is ~8 days of voting
# twice daily, versus /daily's 30 calendar days.
VOTE_MATERIAL_TIER_STREAK_THRESHOLDS = [1, 4, 9, 15]  # parallel to MATERIAL_TIERS
VOTE_MATERIAL_BASE_AMOUNT = 12
VOTE_MATERIAL_PER_STREAK = 2

# Guaranteed lootbox per vote, escalating with streak. Starts at epic --
# a tier /daily only reaches at a 7-day streak -- and tops out at mythic,
# the best box in the game (see lootbox_config.LOOTBOX_TEMPLATES).
VOTE_LOOTBOX_PROGRESSION: list[tuple[int, str]] = [
    (1, "epic"),
    (8, "legendary"),
    (20, "mythic"),
]
# Extra bonus box every N consecutive votes, at its own tier.
VOTE_LOOTBOX_MILESTONES = {
    5: "legendary",
    15: "mythic",
}

# Top.gg runs "weekend multiplier" periods where a vote counts double on
# their leaderboard. We mirror that in-game: shards and gold are doubled
# on a weekend vote so the flavour matches what top.gg tells the player.
WEEKEND_MULTIPLIER = 2


def _capped(streak: int) -> int:
    """Streak clamped to VOTE_STREAK_CAP, floored at 1 -- every reward
    curve below scales off this rather than the raw streak."""
    return max(1, min(streak, VOTE_STREAK_CAP))


def compute_vote_currency(streak: int, is_weekend: bool = False) -> tuple[int, int, int]:
    """Returns (shards, gold, reroll_tokens) for a vote claimed at this
    streak length (counted AFTER the increment, like compute_daily_reward).
    Reroll tokens are deliberately flat -- they're a steady utility drip,
    not something to chase a streak for."""
    capped = _capped(streak)

    shards = VOTE_BASE_SHARDS + VOTE_SHARDS_PER_STREAK * (capped - 1)
    if streak % VOTE_SHARD_MILESTONE_INTERVAL == 0:
        shards += VOTE_SHARD_MILESTONE_AMOUNT

    gold = VOTE_BASE_GOLD + VOTE_GOLD_PER_STREAK * (capped - 1)

    if is_weekend:
        shards *= WEEKEND_MULTIPLIER
        gold *= WEEKEND_MULTIPLIER

    return shards, gold, VOTE_REROLL_TOKENS


def compute_vote_materials(streak: int) -> dict[str, int]:
    """Returns {material_value: amount} -- both materials from a
    streak-appropriate tier, escalating in tier and amount together."""
    tier_index = 0
    for i, threshold in enumerate(VOTE_MATERIAL_TIER_STREAK_THRESHOLDS):
        if streak >= threshold:
            tier_index = i

    capped = _capped(streak)
    amount = VOTE_MATERIAL_BASE_AMOUNT + VOTE_MATERIAL_PER_STREAK * (capped - 1)
    return {material.value: amount for material in MATERIAL_TIERS[tier_index]}


def compute_vote_lootboxes(streak: int) -> list[str]:
    """The guaranteed box escalates in tier with the streak; milestone
    streaks grant an additional, separately-tiered box on top."""
    base_tier = VOTE_LOOTBOX_PROGRESSION[0][1]
    for threshold, tier in VOTE_LOOTBOX_PROGRESSION:
        if streak >= threshold:
            base_tier = tier

    tiers = [base_tier]
    for interval, tier in VOTE_LOOTBOX_MILESTONES.items():
        if streak % interval == 0:
            tiers.append(tier)
    return tiers


def next_milestone_in(streak: int) -> int:
    """How many more consecutive votes until the next shard milestone --
    shown on the /vote embed so the streak has a visible near-term goal."""
    return VOTE_SHARD_MILESTONE_INTERVAL - (streak % VOTE_SHARD_MILESTONE_INTERVAL)
