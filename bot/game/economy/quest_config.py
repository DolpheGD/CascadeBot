"""
Pure config for the quest system -- no DB template table needed (quests
are looked up by a fixed string id, snapshotted onto the PlayerQuest row
at assignment time), same pattern as hq_config.HQ_LEVEL_CONFIG /
mailbox_config.MAILBOX_REWARD_TABLE.

Each quest dict has:
  - "id": stable string key, also stored on PlayerQuest.quest_id
  - "description": shown to the player
  - "goal_type": a string key that bot/services/quest_service.py's
    `record_progress()` call sites (scattered through combat_service,
    dungeon_service, daily_service, gacha_service, harvester_service,
    lootbox_service, item_upgrade_service) report progress against
  - "goal_count": how much progress is needed to complete it
  - "reward": {currency: amount} -- applied via currency_service.add_currency
    the moment the quest completes, no separate claim step

See bot/services/quest_service.py for how these get assigned/tracked.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Beginner quests -- seeded once per player (see
# quest_service.ensure_beginner_quests_seeded), each completable exactly
# once ever. Finishing every single one grants BEGINNER_BONUS_REWARD on
# top of their individual rewards (see Player.beginner_quest_bonus_claimed).
# ----------------------------------------------------------------------

BEGINNER_QUESTS: list[dict] = [
    {
        "id": "beginner_first_win",
        "description": "Win a battle.",
        "goal_type": "win_battles",
        "goal_count": 1,
        "reward": {"gold": 75},
    },
    {
        "id": "beginner_first_adventure",
        "description": "Complete an expedition (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 1,
        "reward": {"gold": 75},
    },
    {
        "id": "beginner_first_upgrade",
        "description": "Level up a piece of gear.",
        "goal_type": "upgrade_gear",
        "goal_count": 1,
        "reward": {"reroll_tokens": 5},
    },
    {
        "id": "beginner_first_daily",
        "description": "Claim your daily reward with `/daily`.",
        "goal_type": "claim_daily",
        "goal_count": 1,
        "reward": {"gold": 50},
    },
    {
        "id": "beginner_first_pull",
        "description": "Pull a character with `/pull`.",
        "goal_type": "gacha_pulls",
        "goal_count": 1,
        "reward": {"shards": 15},
    },
    {
        "id": "beginner_first_harvester",
        "description": "Buy your first harvester with `/harvesters`.",
        "goal_type": "buy_harvester",
        "goal_count": 1,
        "reward": {"gold": 75},
    },
    {
        "id": "beginner_first_lootbox",
        "description": "Open a lootbox.",
        "goal_type": "open_lootboxes",
        "goal_count": 1,
        "reward": {"gold": 30},
    },
]

BEGINNER_BONUS_REWARD: dict[str, int] = {"shards": 300}


# ----------------------------------------------------------------------
# Basic quests -- one random pick from this pool, re-rollable every
# BASIC_QUEST_COOLDOWN_HOURS (see quest_service.roll_basic_quest).
# ----------------------------------------------------------------------

BASIC_QUEST_COOLDOWN_HOURS = 5

BASIC_QUEST_POOL: list[dict] = [
    {
        "id": "basic_upgrade_gear",
        "description": "Level up a piece of gear.",
        "goal_type": "upgrade_gear",
        "goal_count": 1,
        "reward": {"gold": 60, "wood": 10, "stone": 10},
    },
    {
        "id": "basic_three_adventures",
        "description": "Complete 3 expeditions (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 3,
        "reward": {"gold": 150, "shards": 5},
    },
    {
        "id": "basic_win_battles",
        "description": "Win 5 battles.",
        "goal_type": "win_battles",
        "goal_count": 5,
        "reward": {"gold": 100, "reroll_tokens": 3},
    },
    {
        "id": "basic_collect_harvesters",
        "description": "Collect from a harvester 2 times.",
        "goal_type": "collect_harvester",
        "goal_count": 2,
        "reward": {"metal": 10, "crystal": 10},
    },
    {
        "id": "basic_open_lootboxes",
        "description": "Open 2 lootboxes.",
        "goal_type": "open_lootboxes",
        "goal_count": 2,
        "reward": {"gold": 80},
    },
    {
        "id": "basic_gacha_pull",
        "description": "Pull the gacha once.",
        "goal_type": "gacha_pulls",
        "goal_count": 1,
        "reward": {"shards": 5},
    },
    {
        "id": "basic_upgrade_gear_twice",
        "description": "Level up gear 2 times.",
        "goal_type": "upgrade_gear",
        "goal_count": 2,
        "reward": {"gold": 100, "wood": 15, "stone": 15, "metal": 5},
    },
    {
        "id": "basic_defeat_boss",
        "description": "Defeat a boss.",
        "goal_type": "defeat_boss",
        "goal_count": 1,
        "reward": {"gold": 120, "shards": 5},
    },
]
