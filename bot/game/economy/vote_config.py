"""
Tuning for the /vote command (top.gg voting rewards). Kept separate from
bot/services/vote_service.py so the curves can be retuned without touching
the claim/streak logic -- same split as daily_config.py and its service.

Deliberately the strongest recurring reward in the game. Top.gg allows one
vote per bot every 12 hours, so a committed player can claim this twice a
day; the numbers below assume that and are set so voting clearly beats
/daily rather than merely matching it. Shards lead the package because
they're the character-gacha currency and the thing players most want a
faucet for, but gold/materials/lootboxes all scale on the streak too.

    BALANCE NOTE. At a 20+ vote streak this pays roughly 4-5x a /daily
    claim per real day (two votes, each bigger than a daily). That is the
    intended "voting is the main progression path" setting -- but it IS a
    large amount of income to add to a live economy, so every knob here is
    a plain module-level constant. If it lands too hot, VOTE_BASE_SHARDS,
    VOTE_BASE_GOLD and the two _PER_STREAK values are the ones to pull
    first; nothing outside this module needs to change.

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

# Shards -- the headline reward. Base is already >2x a /daily claim's 50,
# and grows per consecutive vote up to the cap.
VOTE_BASE_SHARDS = 200
VOTE_SHARDS_PER_STREAK = 20
VOTE_STREAK_CAP = 20  # streak stops scaling any reward past this

# Bonus shards every N consecutive votes, on top of the scaled amount.
VOTE_SHARD_MILESTONE_INTERVAL = 5
VOTE_SHARD_MILESTONE_AMOUNT = 400

# Gold and reroll tokens -- generous but not the point of voting.
VOTE_BASE_GOLD = 400
VOTE_GOLD_PER_STREAK = 60
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
