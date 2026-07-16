"""
Tuning for the /daily command. Kept separate from the service so reward
curves can be retuned without touching the claim logic.
"""

from __future__ import annotations

DAILY_BASE_GOLD = 100
DAILY_GOLD_PER_STREAK_DAY = 15   # additional gold per consecutive day, capped below
DAILY_STREAK_GOLD_CAP_DAYS = 20  # streak bonus stops growing past this many days

# Bonus shards awarded on top of gold every N days of an unbroken streak.
DAILY_SHARD_MILESTONE_INTERVAL = 7
DAILY_SHARD_MILESTONE_AMOUNT = 10

# Reroll tokens on every claim -- a small, reliable source of the equipment
# reroll/substat currency, separate from dungeon drops. Part of making
# dailies feel more impactful now that dungeon gold was trimmed down.
DAILY_REROLL_TOKENS = 3

# Lootbox tiers granted alongside gold/shards. Every claim grants a Common
# box; hitting a weekly/monthly streak milestone grants a better one too
# (in addition to, not instead of, the Common).
DAILY_LOOTBOX_BASE_TIER = "rare"
DAILY_LOOTBOX_MILESTONES = {
    7: "epic",
    30: "legendary",
}

# A streak survives if the player claims again within this many hours of
# their last claim (so claiming daily-ish, not exactly every 24h, still
# counts). Claiming again before 24h has passed is blocked entirely.
DAILY_COOLDOWN_HOURS = 24
DAILY_STREAK_GRACE_HOURS = 48


def compute_daily_reward(streak: int) -> tuple[int, int, int]:
    """Returns (gold, shards, reroll_tokens) for the given streak length (after increment)."""
    capped_streak = min(streak, DAILY_STREAK_GOLD_CAP_DAYS)
    gold = DAILY_BASE_GOLD + DAILY_GOLD_PER_STREAK_DAY * (capped_streak - 1)

    shards = 0
    if streak % DAILY_SHARD_MILESTONE_INTERVAL == 0:
        shards = DAILY_SHARD_MILESTONE_AMOUNT

    return gold, shards, DAILY_REROLL_TOKENS


def compute_daily_lootboxes(streak: int) -> list[str]:
    """Every claim grants the base tier; milestone streaks grant an
    additional, better tier on top."""
    tiers = [DAILY_LOOTBOX_BASE_TIER]
    for milestone_days, tier in DAILY_LOOTBOX_MILESTONES.items():
        if streak % milestone_days == 0:
            tiers.append(tier)
    return tiers
