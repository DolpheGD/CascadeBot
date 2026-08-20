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
        "reward": {"cores": 120},
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

    # ------------------------------------------------------------------
    # THE THREE THAT TAKE MORE THAN ONE PRESS.
    #
    # Every quest above completes the first time you do the thing, which
    # made the whole beginner set a checklist of firsts you could finish
    # in one sitting without engaging with anything. That was fine when
    # the completion bonus was small; against 1,200 shards it is not --
    # the reward should mean the player has actually PLAYED, not that
    # they clicked each button once.
    #
    # So the set now ends on three that take real progress, chosen to
    # point at the three systems a new player otherwise bounces off:
    # the base, depth, and repeat expeditions.
    #
    # Both of the first two are HIGH-WATER goals -- see
    # quest_service.HIGH_WATER_GOALS. Their `amount` is a level or a
    # floor reached, not a count, so they cannot be satisfied by
    # repetition at a shallower depth.
    # ------------------------------------------------------------------
    {
        "id": "beginner_hq_two",
        "description": "Upgrade Cascade HQ to level 2 with `/base`.",
        "goal_type": "hq_level",
        "goal_count": 2,
        "reward": {"gold": 400, "wood": 60, "stone": 60},
    },
    {
        "id": "beginner_floor_twenty",
        "description": "Reach floor 20 of an expedition.",
        "goal_type": "reach_floor",
        "goal_count": 20,
        "reward": {"gold": 600, "cores": 240, "evolution_fragments": 40},
    },
]

# ----------------------------------------------------------------------
# THE POST-TUTORIAL TEN-PULL.
#
# 1,200 shards is exactly ten pulls, which is the shape every gacha uses
# to end its tutorial: you finish the introduction and you get one full
# multi, so your first real roster decision is made with a handful of
# characters rather than one.
#
# It is deliberately NOT paid on a timer or by playing -- it is paid for
# finishing all eight beginner objectives, which between them require
# winning a fight, running an expedition, levelling gear, pulling, buying
# a harvester, opening a box and beating an elite. A player who has done
# all of that has seen the whole game and earned a real roster.
#
# Worth recording that this was briefly cut to 240, on the theory that a
# 900-shard lump was drowning the prologue's own pacing. That diagnosis
# was wrong: the ~480 shards a new player was finishing the prologue with
# came from the PROLOGUE (four deliberate 120-shard grants), not from
# here. Cutting this fixed nothing and made the tutorial payout worse, so
# it is not only restored but raised to the round number it should always
# have been.
# ----------------------------------------------------------------------
# EXACTLY 1,200 SHARDS ACROSS THE WHOLE SET, not 1,200 plus change.
#
# The individual quests used to pay small shard amounts on top of this,
# so the advertised "ten pulls for finishing the tutorial" actually came
# to 1,284 -- a number that is worse than 1,200 precisely because it is
# not a round number of pulls. The stray 84 bought nothing and made the
# headline a lie.
#
# So the individual quests pay GOLD, MATERIALS and CORES, and shards
# arrive in one lump here. Cores are spread across the individual
# rewards rather than added to this bonus for the opposite reason: the
# card banner should be something a new player touches DURING the
# beginner set, not a second lump at the end of it.
BEGINNER_BONUS_REWARD: dict[str, int] = {"shards": 1200, "cores": 600,
                                         "evolution_fragments": 120}


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


# ======================================================================
# COMMISSIONS
# ======================================================================
#
# A third quest kind, sharing the PlayerQuest table with beginner and
# basic quests and riding the SAME record_progress() plumbing -- which is
# the entire reason they are cheap to add. A commission is a named,
# written contract taken from the board in Team Cascade's yard, and it is
# deliberately the one quest type that sends the player OUT of the story
# and into adventure mode.
#
# Three things make them different from basic quests:
#
#   * They are TAKEN, not assigned. The player walks to the board tile
#     and chooses one, so a commission is always something they opted
#     into rather than something the cooldown handed them.
#   * They are CLAIMED. Finishing the goal does not pay out; returning to
#     the board does. That is what makes the board worth walking back to,
#     and it is why record_progress skips the auto-grant for this kind
#     (see quest_service._grant_reward's caller).
#   * They can be REGION-SCOPED. "Defeat three elites" is a basic quest.
#     "Defeat three elites in the Hotlands" is a commission, and it works
#     because dungeon_service reports progress against both the plain
#     goal type and a region-qualified one -- see REGION_SCOPED_GOALS.
#
# Fields:
#   id              stable key, stored on PlayerQuest.quest_id
#   name            the contract's title, shown on the board
#   giver           who posted it, for flavour and for the claim line
#   description     the ask, in the giver's voice
#   goal_type       plain key, or "<key>@<region>" for a region-scoped one
#   goal_count      how much
#   reward          {currency: amount}
#   requires_mission  story mission id that must be COMPLETE before this
#                     contract appears on the board. Keeps early players
#                     from taking Abyssnia work they cannot survive.
#   repeatable      may be taken again after claiming (default False)
#
# Rewards are deliberately fatter than basic quests and lean on
# evolution fragments and cores, because the point of a commission is to
# convert adventure-mode effort into story-mode power.

# Goal types that dungeon_service also reports in a region-qualified
# form, as "<goal_type>@<region name>". Anything NOT in this set cannot
# be region-scoped in a commission, and tools/check_commissions.py
# enforces that -- a commission scoped to a goal nobody reports that way
# would sit at 0 progress forever and look exactly like a working one.
REGION_SCOPED_GOALS = {"win_battles", "defeat_boss", "defeat_elite",
                       "complete_adventures"}

COMMISSIONS: list[dict] = [
    # ---- early: Glacier 15, available as soon as the Aligners are in play ----
    {
        "id": "com_ice_survey",
        "name": "Ice Survey, Paid",
        "giver": "Josh",
        "description": (
            "Glacier 15. Two full runs, start to finish. I don't care what "
            "you bring back, I care that the route still works -- we've been "
            "sending people up there on the assumption that it does."
        ),
        "goal_type": "complete_adventures@Glacier 15",
        "goal_count": 2,
        "reward": {"gold": 3200, "evolution_fragments": 180, "cores": 220},
        "requires_mission": "c1m2_the_pitch",
    },
    {
        "id": "com_thin_the_drones",
        "name": "Thin Them Out",
        "giver": "Blueflame",
        "description": (
            "Drones on the glacier have started travelling in threes. That's "
            "new. Win twelve fights up there and I'll know whether it's a "
            "pattern or whether I'm being paranoid again."
        ),
        "goal_type": "win_battles@Glacier 15",
        "goal_count": 12,
        "reward": {"gold": 4100, "evolution_fragments": 220, "shards": 140},
        "requires_mission": "c1m3_ashfield",
        "repeatable": True,
    },

    # ---- mid: the Wastelands, once the North is open ----
    {
        "id": "com_wasteland_elites",
        "name": "The Ones Giving Orders",
        "giver": "Jofrog",
        "description": (
            "Wastelands. Four elites, and I want them specifically -- not the "
            "rank and file. Somebody out there is organising, and organisers "
            "keep notes."
        ),
        "goal_type": "defeat_elite@The Wastelands",
        "goal_count": 4,
        "reward": {"gold": 8600, "evolution_fragments": 420, "cores": 560},
        "requires_mission": "c2m2_the_border",
        "repeatable": True,
    },
    {
        "id": "com_dolpo_shipping",
        "name": "A Favour, Not A Job",
        "giver": "Dolpo",
        "description": (
            "My brother says you're reliable. I'd like to find out cheaply. "
            "Three complete runs through the Wastelands -- and if anything "
            "down there has HHyper's mark on it, remember where."
        ),
        "goal_type": "complete_adventures@The Wastelands",
        "goal_count": 3,
        "reward": {"gold": 11000, "evolution_fragments": 500, "echoes": 40},
        "requires_mission": "c2m3_dolpo",
    },

    # ---- late-mid: the Hotlands, from Chapter Three ----
    {
        "id": "com_hotlands_bosses",
        "name": "Three Doors Down",
        "giver": "Rex",
        "description": (
            "Hotlands. Three bosses. I am not sending you for the loot, I am "
            "sending you because I want to know if they're still the same "
            "three, or if something has been rebuilding them."
        ),
        "goal_type": "defeat_boss@The Hotlands",
        "goal_count": 3,
        "reward": {"gold": 22000, "evolution_fragments": 900, "cores": 1400},
        "requires_mission": "c3m4_what_he_was_building",
        "repeatable": True,
    },
    {
        "id": "com_forge_backlog",
        "name": "The Backlog",
        "giver": "Chary",
        "description": (
            "Everyone wants their gear upgraded and nobody wants to bring me "
            "materials. Upgrade fifteen pieces yourself and you'll understand "
            "why I've started charging."
        ),
        "goal_type": "upgrade_gear",
        "goal_count": 15,
        "reward": {"gold": 18000, "evolution_fragments": 760, "metal": 120,
                   "crystal": 80},
        "requires_mission": "c3m2_level_a",
        "repeatable": True,
    },

    # ---- late: Voidcrest, from Chapter Four ----
    {
        "id": "com_voidcrest_sweep",
        "name": "Nothing To Report",
        "giver": "Refender",
        "description": (
            "Voidcrest. Four full runs. Every audit team Rohan sent there "
            "filed the same clean report, which is the least believable thing "
            "I have ever read. Go and file a different one."
        ),
        "goal_type": "complete_adventures@Voidcrest Desert",
        "goal_count": 4,
        "reward": {"gold": 46000, "evolution_fragments": 1600, "cores": 2400,
                   "void": 90},
        "requires_mission": "c4m3_what_his_hands_remember",
    },
    {
        "id": "com_dolphin_wants_to_help",
        "name": "Let Me Come",
        "giver": "Dolphin",
        "description": (
            "I know I'm not on the roster. I know. But I've been reading the "
            "run logs and I think I could be useful, and I'd like one chance "
            "to prove it before somebody decides for me. Twenty wins. Any "
            "region. I'll keep count."
        ),
        "goal_type": "win_battles",
        "goal_count": 20,
        "reward": {"gold": 38000, "evolution_fragments": 1400, "echoes": 120},
        "requires_mission": "c4m5_the_open_entry",
    },

    # ---- endgame: Abyssnia, after the story ----
    {
        "id": "com_abyssnia_standing",
        "name": "Standing Order",
        "giver": "Josh",
        "description": (
            "The desk is empty and the work isn't finished. Abyssnia, two "
            "complete runs, and this one renews -- I'd rather it stayed a "
            "standing order than became somebody's last request."
        ),
        "goal_type": "complete_adventures@Abyssnia",
        "goal_count": 2,
        "reward": {"gold": 120000, "evolution_fragments": 3600, "cores": 5200,
                   "entropy": 140},
        "requires_mission": "c5m6_nothing_to_file",
        "repeatable": True,
    },
    # ---- region six ----
    {
        "id": "com_deepworks_survey",
        "name": "Nobody Filed A Closure",
        "giver": "Jofrog",
        "description": (
            "Entrospire never filed a closure notice for the Deepworks. Not "
            "a bankruptcy, not a sale, not a decommission — the paperwork "
            "just stops. Three complete runs down there. I want to know what "
            "it's still making."
        ),
        "goal_type": "complete_adventures@Entrospire Deepworks",
        "goal_count": 3,
        "reward": {"gold": 180000, "evolution_fragments": 5200, "cores": 7400,
                   "entropy": 220},
        "requires_mission": "c5m6_nothing_to_file",
        "repeatable": True,
    },
    {
        "id": "com_the_night_shift",
        "name": "Whatever's Running The Night Shift",
        "giver": "Dolpo",
        "description": (
            "My brother worked a floor like that one. He came home wrong and "
            "he came home lucky, and I've spent nine years not asking which "
            "of those did more. Six elites. I'll pay for every one."
        ),
        "goal_type": "defeat_elite@Entrospire Deepworks",
        "goal_count": 6,
        "reward": {"gold": 96000, "evolution_fragments": 3100, "echoes": 260},
        "requires_mission": "c5m6_nothing_to_file",
        "repeatable": True,
    },
]

# At most this many commissions may be held at once. Low on purpose: a
# commission is meant to shape what the player does next, and holding six
# of them at once means it shapes nothing.
MAX_ACTIVE_COMMISSIONS = 2
