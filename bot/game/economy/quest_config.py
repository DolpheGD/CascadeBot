"""
Pure config for the quest system -- no DB template table needed (quests
are looked up by a fixed string id, snapshotted onto the PlayerQuest row
at assignment time), same pattern as hq_config.HQ_LEVEL_CONFIG /
the other economy configs.

Each quest dict has:
  - "id": stable string key, also stored on PlayerQuest.quest_id
  - "description": shown to the player
  - "goal_type": a string key that bot/services/quest_service.py's
    `record_progress()` call sites (scattered through combat_service,
    dungeon_service, daily_service, character_gacha_service, harvester_service,
    lootbox_service, item_upgrade_service, vote_service) report progress
    against. Valid values: "win_battles", "defeat_boss", "defeat_elite",
    "complete_adventures", "upgrade_gear", "claim_daily", "gacha_pulls",
    "buy_harvester", "collect_harvester", "open_lootboxes", "vote" -- see
    dungeon_service.resolve_battle_end for the "defeat_elite"/
    "defeat_boss"/"win_battles" split.

    A "vote" quest only ever advances on an instance with top.gg voting
    configured (TOPGG_TOKEN set). Keep such quests out of BEGINNER_QUESTS
    for that reason -- a beginner quest that can never complete would
    permanently block the one-time completion bonus. In the weighted
    BASIC_QUEST_POOL an unreachable quest is only ever a reroll away, so
    it's safe there.
  - "goal_count": how much progress is needed to complete it
  - "reward": {currency: amount} -- applied via currency_service.add_currency
    the moment the quest completes, no separate claim step. Any key in
    currency_service.VALID_CURRENCIES is fair game, including the
    region-specific materials (xendium, permafrost_ore, void, entropy),
    not just gold/shards -- gives higher-tier basic quests a reason to
    feel distinct from the low-tier ones beyond raw amount.
  - "weight" (basic pool only, optional, default 10): relative odds this
    entry is picked by roll_basic_quest's weighted draw. Quick/cheap
    quests should skew high (15-20) so they show up often; big grindy
    asks should skew low (3-6) so they're a rarer, bigger-payoff pick
    rather than something the player is stuck rerolling around
    constantly. BEGINNER_QUESTS ignores weight entirely (every entry is
    seeded at once, not drawn).

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
        "reward": {"gold": 120},
    },
    {
        "id": "beginner_first_adventure",
        "description": "Complete an expedition (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 1,
        "reward": {"gold": 120},
    },
    {
        "id": "beginner_first_upgrade",
        "description": "Level up a piece of gear.",
        "goal_type": "upgrade_gear",
        "goal_count": 1,
        "reward": {"reroll_tokens": 8},
    },
    {
        "id": "beginner_first_daily",
        "description": "Claim your daily reward with `/daily`.",
        "goal_type": "claim_daily",
        "goal_count": 1,
        "reward": {"gold": 80},
    },
    {
        "id": "beginner_first_pull",
        "description": "Pull a character with `/pull`.",
        "goal_type": "gacha_pulls",
        "goal_count": 1,
        "reward": {"shards": 24},
    },
    {
        "id": "beginner_first_harvester",
        "description": "Buy your first harvester with `/harvesters`.",
        "goal_type": "buy_harvester",
        "goal_count": 1,
        "reward": {"gold": 120},
    },
    {
        "id": "beginner_first_lootbox",
        "description": "Open a lootbox.",
        "goal_type": "open_lootboxes",
        "goal_count": 1,
        "reward": {"gold": 48},
    },
    {
        "id": "beginner_first_elite",
        "description": "Defeat an elite encounter.",
        "goal_type": "defeat_elite",
        "goal_count": 1,
        "reward": {"gold": 96, "reroll_tokens": 3},
    },
]

BEGINNER_BONUS_REWARD: dict[str, int] = {"shards": 900}


# ----------------------------------------------------------------------
# Basic quests -- one random pick from this pool, re-rollable every
# BASIC_QUEST_COOLDOWN_HOURS (see quest_service.roll_basic_quest).
# ----------------------------------------------------------------------

BASIC_QUEST_COOLDOWN_HOURS = 5

# Reward pass: every reward in this file (BEGINNER_QUESTS, BASIC_QUEST_POOL,
# BEGINNER_BONUS_REWARD) was bumped roughly 60-70% above its original value
# as part of a "quests should feel worth doing" pass.

# How many basic quests a player can hold ACTIVE at once (was a hard cap of
# 1). Filling an empty slot is always instant/free -- no cooldown -- since
# completing a quest (or never having rolled one at all) should let a
# player jump straight back in; BASIC_QUEST_COOLDOWN_HOURS only gates
# abandoning a specific STILL-ACTIVE quest early for a different one (see
# quest_service.reroll_basic_quest), preventing cherry-picking an easy
# quest by spamming rerolls the way the old single-slot system could.
MAX_ACTIVE_BASIC_QUESTS = 3

BASIC_QUEST_POOL: list[dict] = [
    # ---- vote ----
    # Low weight: /vote is on a 12h cooldown regardless, so this can't be
    # cleared on demand the way the others can, and on an instance without
    # TOPGG_TOKEN set it can't be cleared at all (see the module docstring).
    {
        "id": "basic_vote",
        "description": "Vote for CascadeBot on top.gg.",
        "goal_type": "vote",
        "goal_count": 1,
        "reward": {"shards": 60, "gold": 150},
        "weight": 5,
    },
    # ---- upgrade_gear ----
    {
        "id": "basic_upgrade_gear",
        "description": "Level up a piece of gear.",
        "goal_type": "upgrade_gear",
        "goal_count": 1,
        "reward": {"gold": 100, "wood": 17, "stone": 17},
        "weight": 18,
    },
    {
        "id": "basic_upgrade_gear_twice",
        "description": "Level up gear 2 times.",
        "goal_type": "upgrade_gear",
        "goal_count": 2,
        "reward": {"gold": 170, "wood": 26, "stone": 26, "metal": 8},
        "weight": 12,
    },
    {
        "id": "basic_upgrade_gear_thrice",
        "description": "Level up gear 3 times.",
        "goal_type": "upgrade_gear",
        "goal_count": 3,
        "reward": {"gold": 305, "wood": 42, "stone": 42, "metal": 17, "crystal": 8},
        "weight": 6,
    },

    # ---- complete_adventures ----
    {
        "id": "basic_one_adventure",
        "description": "Complete an expedition (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 1,
        "reward": {"gold": 120},
        "weight": 18,
    },
    {
        "id": "basic_three_adventures",
        "description": "Complete 3 expeditions (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 3,
        "reward": {"gold": 255, "shards": 8},
        "weight": 12,
    },
    {
        "id": "basic_five_adventures",
        "description": "Complete 5 expeditions (win or lose).",
        "goal_type": "complete_adventures",
        "goal_count": 5,
        "reward": {"gold": 440, "shards": 14, "reroll_tokens": 5},
        "weight": 6,
    },

    # ---- win_battles ----
    {
        "id": "basic_win_battles",
        "description": "Win 5 battles.",
        "goal_type": "win_battles",
        "goal_count": 5,
        "reward": {"gold": 170, "reroll_tokens": 5},
        "weight": 14,
    },
    {
        "id": "basic_win_battles_ten",
        "description": "Win 10 battles.",
        "goal_type": "win_battles",
        "goal_count": 10,
        "reward": {"gold": 375, "reroll_tokens": 10, "shards": 8},
        "weight": 8,
    },
    {
        "id": "basic_win_battles_twenty",
        "description": "Win 20 battles.",
        "goal_type": "win_battles",
        "goal_count": 20,
        "reward": {"gold": 765, "reroll_tokens": 20, "shards": 17},
        "weight": 4,
    },

    # ---- defeat_elite ----
    {
        "id": "basic_defeat_elite",
        "description": "Defeat an elite encounter.",
        "goal_type": "defeat_elite",
        "goal_count": 1,
        "reward": {"gold": 155, "reroll_tokens": 3},
        "weight": 14,
    },
    {
        "id": "basic_defeat_elite_twice",
        "description": "Defeat 2 elite encounters.",
        "goal_type": "defeat_elite",
        "goal_count": 2,
        "reward": {"gold": 340, "shards": 10, "reroll_tokens": 7},
        "weight": 7,
    },
    {
        "id": "basic_defeat_elite_thrice",
        "description": "Defeat 3 elite encounters.",
        "goal_type": "defeat_elite",
        "goal_count": 3,
        "reward": {"gold": 580, "shards": 20, "reroll_tokens": 10},
        "weight": 4,
    },

    # ---- defeat_boss ----
    {
        "id": "basic_defeat_boss",
        "description": "Defeat a boss.",
        "goal_type": "defeat_boss",
        "goal_count": 1,
        "reward": {"gold": 205, "shards": 8},
        "weight": 10,
    },
    {
        "id": "basic_defeat_boss_twice",
        "description": "Defeat 2 bosses.",
        "goal_type": "defeat_boss",
        "goal_count": 2,
        "reward": {"gold": 440, "shards": 17, "reroll_tokens": 7},
        "weight": 4,
    },

    # ---- collect_harvester ----
    {
        "id": "basic_collect_harvesters",
        "description": "Collect from a harvester 2 times.",
        "goal_type": "collect_harvester",
        "goal_count": 2,
        "reward": {"metal": 17, "crystal": 17},
        "weight": 14,
    },
    {
        "id": "basic_collect_harvesters_four",
        "description": "Collect from a harvester 4 times.",
        "goal_type": "collect_harvester",
        "goal_count": 4,
        "reward": {"metal": 34, "crystal": 34, "gold": 100},
        "weight": 8,
    },
    {
        "id": "basic_collect_harvesters_six",
        "description": "Collect from a harvester 6 times.",
        "goal_type": "collect_harvester",
        "goal_count": 6,
        "reward": {"metal": 60, "crystal": 60, "gold": 205, "xendium": 8},
        "weight": 4,
    },

    # ---- open_lootboxes ----
    {
        "id": "basic_open_lootbox_one",
        "description": "Open a lootbox.",
        "goal_type": "open_lootboxes",
        "goal_count": 1,
        "reward": {"gold": 68},
        "weight": 16,
    },
    {
        "id": "basic_open_lootboxes",
        "description": "Open 2 lootboxes.",
        "goal_type": "open_lootboxes",
        "goal_count": 2,
        "reward": {"gold": 135},
        "weight": 12,
    },
    {
        "id": "basic_open_lootboxes_four",
        "description": "Open 4 lootboxes.",
        "goal_type": "open_lootboxes",
        "goal_count": 4,
        "reward": {"gold": 305, "shards": 8},
        "weight": 6,
    },

    # ---- gacha_pulls ----
    {
        "id": "basic_gacha_pull",
        "description": "Pull the gacha once.",
        "goal_type": "gacha_pulls",
        "goal_count": 1,
        "reward": {"shards": 8},
        "weight": 15,
    },
    {
        "id": "basic_gacha_pull_thrice",
        "description": "Pull the gacha 3 times.",
        "goal_type": "gacha_pulls",
        "goal_count": 3,
        "reward": {"shards": 26, "gold": 84},
        "weight": 7,
    },
]
