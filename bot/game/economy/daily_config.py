"""
Tuning for the /daily command. Kept separate from the service so reward
curves can be retuned without touching the claim logic.
"""

from __future__ import annotations

from bot.database.models.enums import MaterialType

DAILY_BASE_GOLD = 100
DAILY_GOLD_PER_STREAK_DAY = 15   # additional gold per consecutive day, capped below
DAILY_STREAK_GOLD_CAP_DAYS = 20  # streak bonus stops growing past this many days

# Bonus shards awarded on top of gold every N days of an unbroken streak.
DAILY_SHARD_MILESTONE_INTERVAL = 7
DAILY_SHARD_MILESTONE_AMOUNT = 150

# Reroll tokens on every claim -- a small, reliable source of the equipment
# reroll/substat currency, separate from dungeon drops. Part of making
# dailies feel more impactful now that dungeon gold was trimmed down.
DAILY_REROLL_TOKENS = 10

# Lootbox tier for the guaranteed daily box escalates with streak length --
# starts at "rare" (not "common": /daily should feel worth doing from day
# one) and gradually climbs the longer the streak holds. Milestone streaks
# ALSO grant an extra bonus box on top, at its own (usually higher) tier.
DAILY_LOOTBOX_BASE_PROGRESSION: list[tuple[int, str]] = [
    (1, "rare"),
    (7, "epic"),
    (30, "legendary"),
]
DAILY_LOOTBOX_MILESTONES = {
    7: "epic",
    30: "legendary",
}

# Material reward on every claim -- both materials from a streak-
# appropriate tier (same tier groupings harvesters/dungeon drops use, see
# MaterialType.tier), gradually escalating in tier and amount the longer
# an unbroken streak runs, same spirit as the lootbox progression above.
DAILY_MATERIAL_TIERS: list[tuple[MaterialType, MaterialType]] = [
    (MaterialType.WOOD, MaterialType.STONE),
    (MaterialType.METAL, MaterialType.CRYSTAL),
    (MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE),
    (MaterialType.VOID, MaterialType.ENTROPY),
]
DAILY_MATERIAL_TIER_STREAK_THRESHOLDS = [1, 7, 14, 30]  # parallel to DAILY_MATERIAL_TIERS
DAILY_MATERIAL_BASE_AMOUNT = 5
DAILY_MATERIAL_PER_STREAK_DAY = 1
DAILY_MATERIAL_STREAK_CAP_DAYS = 20

# A streak survives if the player claims again within this many hours of
# their last claim (so claiming daily-ish, not exactly every 24h, still
# counts). Claiming again before 24h has passed is blocked entirely.
DAILY_COOLDOWN_HOURS = 24
DAILY_STREAK_GRACE_HOURS = 48


def compute_daily_reward(streak: int) -> tuple[int, int, int]:
    """Returns (gold, shards, reroll_tokens) for the given streak length (after increment)."""
    capped_streak = min(streak, DAILY_STREAK_GOLD_CAP_DAYS)
    gold = DAILY_BASE_GOLD + DAILY_GOLD_PER_STREAK_DAY * (capped_streak - 1)

    shards = 50
    if streak % DAILY_SHARD_MILESTONE_INTERVAL == 0:
        shards += DAILY_SHARD_MILESTONE_AMOUNT

    return gold, shards, DAILY_REROLL_TOKENS


def compute_daily_lootboxes(streak: int) -> list[str]:
    """The guaranteed base-tier box escalates in tier as the streak grows
    (see DAILY_LOOTBOX_BASE_PROGRESSION); milestone streaks grant an
    additional, separately-tiered bonus box on top."""
    base_tier = DAILY_LOOTBOX_BASE_PROGRESSION[0][1]
    for threshold, tier in DAILY_LOOTBOX_BASE_PROGRESSION:
        if streak >= threshold:
            base_tier = tier

    tiers = [base_tier]
    for milestone_days, tier in DAILY_LOOTBOX_MILESTONES.items():
        if streak % milestone_days == 0:
            tiers.append(tier)
    return tiers


def compute_daily_materials(streak: int) -> dict[str, int]:
    """Returns {material_value: amount}, two materials from a streak-
    appropriate tier, gradually escalating in both tier and amount."""
    tier_index = 0
    for i, threshold in enumerate(DAILY_MATERIAL_TIER_STREAK_THRESHOLDS):
        if streak >= threshold:
            tier_index = i
    materials = DAILY_MATERIAL_TIERS[tier_index]

    capped_streak = min(streak, DAILY_MATERIAL_STREAK_CAP_DAYS)
    amount = DAILY_MATERIAL_BASE_AMOUNT + DAILY_MATERIAL_PER_STREAK_DAY * (capped_streak - 1)

    return {material.value: amount for material in materials}
