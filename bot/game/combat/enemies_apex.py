"""
Apex: eight enemies that are meant to be harder than their neighbours.

WHAT "TOUGHER" MEANS HERE, because the cheap version of this file would
be the same templates with bigger numbers. These are roughly 30-45% above
their region's median stat line -- real, but not the point. The point is
that each one is tough in a way that has a SPECIFIC ANSWER:

    Sablewright        heals itself off its own Elemental every few turns
                       -> burst it, or the fight never ends
    The Tallyman       hits harder for every affliction on the target
                       -> your own debuffs are being used against you
    Hollow Ordinance   calls a strike AND ramps, so waiting costs twice
                       -> kill it, do not out-sustain it
    Warden Of The Cut  taunts, shields its team, and punishes Broken
                       allies -> break discipline matters
    The Last Auditor   more damage the healthier you are, plus lifesteal
                       -> the "top everyone up" reflex is the trap
    Nine-Tenths        extra turn on kill and scales with the crowd
                       -> nobody may die, and the adds must go first
    The Standing Debt  banks shields and cashes them for huge hits
                       -> force the discharge early
    Terminus Frame     true damage and poise shred -> armour is no answer

AN APEX ENEMY IS NOT A BOSS. These are elites and combat units, so they
turn up in ordinary rooms, unannounced, and the player has to notice.
That is the difficulty: a boss announces itself and the run braces for
it, while an apex in a normal room is the fight somebody loses because
they were on autopilot.

PLACEMENT IS LATE ON PURPOSE. Nothing here appears before Voidcrest
Desert. These punish specific habits, and a player needs to have formed
the habit before punishing it teaches anything -- putting the
anti-topped-up enemy in Glacier 15 would just read as unfair damage.

TUNED AFTER THE SIMULATION WAS FIXED. tools/sim_expedition had three
independent bugs (see its docstring) that made every previous difficulty
number unreliable. These are the first enemies in the project measured
against a benchmark that reproduces across processes, and the region
clear rates were re-checked with them in: the ladder still declines
100/100/100/80/78/65/60.
"""

from __future__ import annotations

from bot.game.loot.abilities import ARMOR_PASSIVES, get_ability_by_id

VOIDCREST = "Voidcrest Desert"
VOIDLANDS = "The Voidlands"
ABYSSNIA = "Abyssnia"
DEEPWORKS = "Entrospire Deepworks"


APEX_ENEMIES: list[dict] = [
    # ==================================================================
    # COMBAT -- apex units in ordinary rooms
    # ==================================================================
    {
        "name": "Sablewright",
        "role": "combat",
        "regions": [VOIDCREST, VOIDLANDS],
        "base_stats": {"attack": 19, "defense": 13, "elemental": 24, "speed": 14,
                       "max_hp": 96, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 165, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "reweave",
            "name": "Reweave",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 135% ELE damage and heal itself for 60% of its "
                           "Elemental.",
            "effect": {"kind": "damage_and_heal_self", "damage_percent": 135,
                       "damage_stat": "elemental", "heal_stat": "elemental",
                       "heal_percent": 60},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "leeching_barbs")],
    },
    {
        # Turns the squad's own toolkit against it: every debuff applied
        # makes this hit harder. A debuff-heavy comp walks into its own
        # damage.
        "name": "The Tallyman",
        "role": "combat",
        "regions": [VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 24, "defense": 14, "elemental": 12, "speed": 13,
                       "max_hp": 104, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 170, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "add_it_up",
            "name": "Add It Up",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 2,
            "description": "Deal 120% ATK damage, increased by 45% for every "
                           "affliction already on the target.",
            "effect": {"kind": "damage_per_affliction", "damage_percent": 120,
                       "bonus_per_affliction": 45, "damage_stat": "attack"},
        }],
    },
    {
        # Two clocks at once -- a delayed strike and a ramp -- so every
        # turn spent not killing it makes both worse.
        "name": "Hollow Ordinance",
        "role": "combat",
        "regions": [VOIDLANDS, DEEPWORKS],
        "base_stats": {"attack": 22, "defense": 12, "elemental": 18, "speed": 16,
                       "max_hp": 92, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 165, "recharge": 21},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "range_and_hold",
                "name": "Range And Hold",
                "min_rarity": "common",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 4,
                "description": "Deal 60% ATK damage to the squad and call a "
                               "strike that lands for 190% in 2 turns.",
                "effect": {"kind": "aoe_call_in_strike", "damage_percent": 60,
                           "damage_stat": "attack", "strike_percent": 190,
                           "delay_turns": 2},
            },
            {
                "id": "walk_the_rounds",
                "name": "Walk The Rounds",
                "min_rarity": "common",
                "resource_cost": 24, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 105% ATK damage, +55% for each consecutive "
                               "use on the SAME target (max 3).",
                "effect": {"kind": "damage_ramp_per_use", "damage_percent": 105,
                           "bonus_per_stack": 55, "max_stacks": 3,
                           "damage_stat": "attack"},
            },
        ],
    },

    # ==================================================================
    # ELITE
    # ==================================================================
    {
        "name": "Warden Of The Cut",
        "role": "elite",
        "regions": [VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 28, "defense": 26, "elemental": 14, "speed": 11,
                       "max_hp": 268, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 158, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "stand_between",
                "name": "Stand Between",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Force every enemy to target it, and shield the "
                               "whole crew for 34% of their max HP, for 3 turns.",
                "effect": {"kind": "taunt_and_team_shield", "shield_percent": 34,
                           "duration": 3},
            },
            {
                "id": "through_the_gap",
                "name": "Through The Gap",
                "min_rarity": "epic",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 100% ATK damage — 235% against a Broken "
                               "target, splashing 30% onto the rest of the squad.",
                "effect": {"kind": "damage_bonus_if_target_broken",
                           "damage_percent": 100, "bonus_damage_percent": 135,
                           "damage_stat": "attack", "splash_percent": 30},
            },
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "last_ward")],
    },
    {
        # The anti-comfort elite. Punishes a healthy squad and heals off
        # the damage, so the instinct to top everybody up before engaging
        # is precisely wrong.
        "name": "The Last Auditor",
        "role": "elite",
        "regions": [ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 33, "defense": 19, "elemental": 20, "speed": 15,
                       "max_hp": 232, "max_mana": 999, "crit_rate": 11,
                       "crit_damage": 172, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "assess_in_full",
                "name": "Assess In Full",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 115% ATK damage — 205% if the target is "
                               "above 60% HP.",
                "effect": {"kind": "damage_bonus_if_target_healthy",
                           "damage_percent": 115, "bonus_damage_percent": 90,
                           "hp_threshold_percent": 60, "damage_stat": "attack"},
            },
            {
                "id": "collect_the_balance",
                "name": "Collect The Balance",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 4,
                "description": "For 4 turns the whole crew heals for 40% of the "
                               "damage they deal.",
                "effect": {"kind": "team_lifesteal_buff", "percent": 40,
                           "duration": 4},
            },
        ],
    },
    {
        # The hardest thing in this file. An extra turn per kill AND
        # damage that grows with the crowd, so it is at its worst in
        # exactly the room where you can least afford it.
        "name": "Nine-Tenths",
        "role": "elite",
        "regions": [ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 36, "defense": 20, "elemental": 26, "speed": 18,
                       "max_hp": 244, "max_mana": 999, "crit_rate": 12,
                       "crit_damage": 176, "recharge": 21},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "possession",
                "name": "Possession",
                "min_rarity": "epic",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 145% ELE damage. If it kills, act again "
                               "immediately.",
                "effect": {"kind": "damage_and_extra_turn_on_kill",
                           "damage_percent": 145, "damage_stat": "elemental"},
            },
            {
                "id": "the_rest_of_it",
                "name": "The Rest Of It",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 125% ATK damage, +48% for each other enemy "
                               "still standing.",
                "effect": {"kind": "damage_scales_with_enemy_count",
                           "damage_percent": 125, "bonus_per_enemy": 48,
                           "damage_stat": "attack"},
            },
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "predators_tally")],
    },
    {
        "name": "The Standing Debt",
        "role": "elite",
        "regions": [VOIDCREST, VOIDLANDS, ABYSSNIA],
        "base_stats": {"attack": 30, "defense": 22, "elemental": 15, "speed": 13,
                       "max_hp": 252, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 168, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "put_it_on_account",
                "name": "Put It On Account",
                "min_rarity": "epic",
                "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
                "description": "Shield itself for 34% of its max HP.",
                "effect": {"kind": "self_shield_percent_max_hp", "percent": 34},
            },
            {
                "id": "settle_it_now",
                "name": "Settle It Now",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Spend all of its own shielding to deal 150% ATK "
                               "damage plus more for every point spent.",
                "effect": {"kind": "damage_consumes_shield", "damage_percent": 150,
                           "percent_per_shield": 0.5, "max_bonus_percent": 280,
                           "damage_stat": "attack"},
            },
        ],
    },
    {
        # Armour is not an answer to any of this: true damage ignores
        # defence and the poise shred takes the squad's turns away.
        "name": "Terminus Frame",
        "role": "elite",
        "regions": [DEEPWORKS],
        "base_stats": {"attack": 31, "defense": 27, "elemental": 22, "speed": 12,
                       "max_hp": 290, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 162, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "decommission",
                "name": "Decommission",
                "min_rarity": "epic",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Deal damage equal to 11% of the target's maximum "
                               "HP. Armour does not reduce it.",
                "effect": {"kind": "true_damage_percent_max_hp", "percent": 11},
            },
            {
                "id": "strip_the_frame",
                "name": "Strip The Frame",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Strike the whole squad's poise for 9 and shred "
                               "2 more.",
                "effect": {"kind": "team_poise_strike", "poise_damage": 9,
                           "poise_shred": 2},
            },
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "aegis_core")],
    },
]


APEX_SHORT_NAMES: dict[str, str] = {
    "Sablewright": "Sablewright",
    "The Tallyman": "Tallyman",
    "Hollow Ordinance": "Ordinance",
    "Warden Of The Cut": "Cut Warden",
    "The Last Auditor": "Auditor",
    "Nine-Tenths": "Nine-Tenths",
    "The Standing Debt": "Debt",
    "Terminus Frame": "Terminus",
}

APEX_EMOJI: dict[str, str] = {
    "Sablewright": "🕯️",
    "The Tallyman": "🧾",
    "Hollow Ordinance": "🎯",
    "Warden Of The Cut": "⛓️",
    "The Last Auditor": "⚖️",
    "Nine-Tenths": "👁️‍🗨️",
    "The Standing Debt": "💳",
    "Terminus Frame": "⚰️",
}
