"""
Ocellios Labs: the hardest roster in the game.

WHERE THIS IS. Ocellios is where the game opens -- the Player wakes here
mid-collapse with Stubby's mechs hacked hostile and escapes east into
Glacier 15. Axel was a test subject in this building. Stubby founded it,
Void-matter synthesis came out of it, and every rumour in the setting
about disappearances and unauthorised experiments points back at it.

So the final region is the first room, and the roster is written to that:
these are not soldiers or machinery, they are EXPERIMENTS. Things that
were made here, mostly on purpose, mostly still running.

WHAT MAKES IT THE ULTIMATE CHALLENGE, and it is not the stat line. Stats
are roughly 35-50% above Entrospire's, which matters but is the least
interesting part. The design rule is STACKING: every template here
combines two mechanics that are individually dangerous elsewhere, so the
counterplay a player learned for each one separately stops being
sufficient.

    Subject 14          extra turn on kill AND scales with the crowd
    Vivisection Rig     true damage AND poise shred -- armour answers neither
    The Waking Ward     heals the crew AND cleanses their debuffs
    Containment Breach  ramps AND calls a delayed strike
    Grafting Bench      shields the crew AND punishes Broken targets
    Subject 03          hits hardest at FULL HP and lifesteals off it
    The Long Experiment banks shields, spends them, and heals off the hit

Elsewhere in the game each of those is one enemy's whole identity. Here
they arrive two at a time, four or five to a room.

THE FINALE IS STUBBY. The reclusive inventor who founded Ocellios, built
the mechs that were hacked hostile on the night the Player woke up, and
has been in this building the entire game. "Stubby's Failsafe" already
exists as an Abyssnia elite -- the thing he left running. This is the man
himself, and he is the hardest single encounter in CascadeBot.

TUNED AGAINST A BENCHMARK THAT REPRODUCES. tools/sim_expedition had three
independent bugs until this session (see its docstring); every difficulty
number in this project before that was a sample of one from an unknown
distribution. These are measured, repeatedly, across processes.
"""

from __future__ import annotations

from bot.game.loot.abilities import ARMOR_PASSIVES, get_ability_by_id

OCELLIOS = "Ocellios Labs"


OCELLIOS_ENEMIES: list[dict] = [
    # ==================================================================
    # COMBAT
    # ==================================================================
    {
        "name": "Subject 14",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 30, "defense": 16, "elemental": 24, "speed": 18,
                       "max_hp": 132, "max_mana": 999, "crit_rate": 11,
                       "crit_damage": 174, "recharge": 21},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "cascade_kill",
                "name": "Cascade",
                "min_rarity": "common",
                "resource_cost": 26, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 140% ELE damage. If it kills, act again "
                               "immediately.",
                "effect": {"kind": "damage_and_extra_turn_on_kill",
                           "damage_percent": 140, "damage_stat": "elemental"},
            },
            {
                "id": "the_others_too",
                "name": "The Others Too",
                "min_rarity": "common",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 115% ATK damage, +45% for each other enemy "
                               "still standing.",
                "effect": {"kind": "damage_scales_with_enemy_count",
                           "damage_percent": 115, "bonus_per_enemy": 45,
                           "damage_stat": "attack"},
            },
        ],
    },
    {
        "name": "Vivisection Rig",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 26, "defense": 22, "elemental": 18, "speed": 13,
                       "max_hp": 150, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 162, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "open_it_up",
                "name": "Open It Up",
                "min_rarity": "common",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Deal damage equal to 10% of the target's maximum "
                               "HP. Armour does not reduce it.",
                "effect": {"kind": "true_damage_percent_max_hp", "percent": 10},
            },
            {
                "id": "hold_still",
                "name": "Hold Still",
                "min_rarity": "common",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Strike the whole squad's poise for 8 and shred "
                               "2 more.",
                "effect": {"kind": "team_poise_strike", "poise_damage": 8,
                           "poise_shred": 2},
            },
        ],
    },
    {
        "name": "The Waking Ward",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 21, "defense": 20, "elemental": 26, "speed": 15,
                       "max_hp": 145, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 158, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "revive_the_ward",
                "name": "Revive The Ward",
                "min_rarity": "common",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 4,
                "description": "Heal the whole crew, scaling off its Elemental.",
                "effect": {"kind": "team_heal_from_stat", "stat": "elemental",
                           "percent": 700},
            },
            {
                "id": "flush_the_lines",
                "name": "Flush The Lines",
                "min_rarity": "common",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Clear every debuff from its crew and shield them "
                               "all for 28% of their max HP.",
                "effect": {"kind": "team_shield_and_cleanse", "shield_percent": 28},
            },
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "medics_covenant")],
    },
    {
        "name": "Containment Breach",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 29, "defense": 15, "elemental": 22, "speed": 19,
                       "max_hp": 126, "max_mana": 999, "crit_rate": 10,
                       "crit_damage": 170, "recharge": 22},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "spread_the_alarm",
                "name": "Spread The Alarm",
                "min_rarity": "common",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 4,
                "description": "Deal 65% ATK damage to the squad and call a "
                               "strike that lands for 200% in 2 turns.",
                "effect": {"kind": "aoe_call_in_strike", "damage_percent": 65,
                           "damage_stat": "attack", "strike_percent": 200,
                           "delay_turns": 2},
            },
            {
                "id": "it_learns",
                "name": "It Learns",
                "min_rarity": "common",
                "resource_cost": 26, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 110% ATK damage, +60% for each consecutive "
                               "use on the SAME target (max 3).",
                "effect": {"kind": "damage_ramp_per_use", "damage_percent": 110,
                           "bonus_per_stack": 60, "max_stacks": 3,
                           "damage_stat": "attack"},
            },
        ],
    },
    {
        "name": "Ocellios Orderly",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 24, "defense": 24, "elemental": 16, "speed": 14,
                       "max_hp": 158, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 158, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "escort_to_theatre",
            "name": "Escort To Theatre",
            "min_rarity": "common",
            "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
            "description": "Force every enemy to target it, and shield the whole "
                           "crew for 30% of their max HP, for 3 turns.",
            "effect": {"kind": "taunt_and_team_shield", "shield_percent": 30,
                       "duration": 3},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "last_ward")],
    },
    {
        "name": "Discarded Iteration",
        "role": "combat",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 27, "defense": 14, "elemental": 20, "speed": 16,
                       "max_hp": 138, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 168, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "spite_of_the_failed",
            "name": "Spite Of The Failed",
            "min_rarity": "common",
            "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
            "description": "Spend 13% of its own HP to hit the whole squad, "
                           "harder the more it spent.",
            "effect": {"kind": "sacrifice_hp_aoe_damage", "self_cost_percent": 13,
                       "damage_percent": 80, "damage_stat": "attack",
                       "hp_scaling": 270},
        }],
    },

    # ==================================================================
    # ELITE
    # ==================================================================
    {
        "name": "Grafting Bench",
        "role": "elite",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 34, "defense": 30, "elemental": 20, "speed": 13,
                       "max_hp": 330, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 164, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "brace_the_frame",
                "name": "Brace The Frame",
                "min_rarity": "epic",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Shield the whole crew for 34% of their max HP.",
                "effect": {"kind": "team_shield_percent_max_hp", "percent": 34},
            },
            {
                "id": "seat_the_graft",
                "name": "Seat The Graft",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 105% ATK damage — 250% against a Broken "
                               "target, splashing 30% onto the rest of the squad.",
                "effect": {"kind": "damage_bonus_if_target_broken",
                           "damage_percent": 105, "bonus_damage_percent": 145,
                           "damage_stat": "attack", "splash_percent": 30},
            },
        ],
    },
    {
        "name": "Subject 03",
        "role": "elite",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 40, "defense": 22, "elemental": 26, "speed": 19,
                       "max_hp": 296, "max_mana": 999, "crit_rate": 13,
                       "crit_damage": 180, "recharge": 21},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "take_it_whole",
                "name": "Take It Whole",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 120% ATK damage — 220% if the target is "
                               "above 60% HP.",
                "effect": {"kind": "damage_bonus_if_target_healthy",
                           "damage_percent": 120, "bonus_damage_percent": 100,
                           "hp_threshold_percent": 60, "damage_stat": "attack"},
            },
            {
                "id": "what_it_was_given",
                "name": "What It Was Given",
                "min_rarity": "epic",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 4,
                "description": "For 4 turns the whole crew heals for 42% of the "
                               "damage they deal.",
                "effect": {"kind": "team_lifesteal_buff", "percent": 42,
                           "duration": 4},
            },
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "leeching_barbs")],
    },
    {
        "name": "The Long Experiment",
        "role": "elite",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 36, "defense": 26, "elemental": 22, "speed": 15,
                       "max_hp": 318, "max_mana": 999, "crit_rate": 10,
                       "crit_damage": 172, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "bank_the_yield",
                "name": "Bank The Yield",
                "min_rarity": "epic",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Shield itself for 36% of its max HP.",
                "effect": {"kind": "self_shield_percent_max_hp", "percent": 36},
            },
            {
                "id": "realise_the_yield",
                "name": "Realise The Yield",
                "min_rarity": "epic",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 2,
                "description": "Spend all of its own shielding to deal 155% ATK "
                               "damage plus more for every point spent.",
                "effect": {"kind": "damage_consumes_shield", "damage_percent": 155,
                           "percent_per_shield": 0.5, "max_bonus_percent": 300,
                           "damage_stat": "attack"},
            },
        ],
    },
    {
        "name": "Void Synthesis Core",
        "role": "elite",
        "regions": [OCELLIOS],
        "base_stats": {"attack": 32, "defense": 24, "elemental": 34, "speed": 16,
                       "max_hp": 305, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 168, "recharge": 22},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "synthesise",
                "name": "Synthesise",
                "min_rarity": "epic",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
                "description": "Raise the crew's attack by 30% and speed by 24% "
                               "for 3 turns.",
                "effect": {"kind": "team_double_buff",
                           "buff_stat_1": "attack", "buff_percent_1": 30,
                           "buff_stat_2": "speed", "buff_percent_2": 24,
                           "duration": 3},
            },
            {
                "id": "vent_the_core",
                "name": "Vent The Core",
                "min_rarity": "epic",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 120% ELE damage to every enemy, with a 55% "
                               "chance to chip 3 extra poise.",
                "effect": {"kind": "aoe_damage_chance_poise_strike",
                           "damage_percent": 120, "damage_stat": "elemental",
                           "poise_chance_percent": 55, "bonus_poise": 3},
            },
        ],
    },

    # ==================================================================
    # BOSSES
    # ==================================================================
    {
        "name": "Theatre Prime",
        "role": "boss",
        "region_roles": {OCELLIOS: "regular"},
        "base_stats": {"attack": 44, "defense": 30, "elemental": 30, "speed": 20,
                       "max_hp": 1650, "max_mana": 999, "crit_rate": 11,
                       "crit_damage": 174, "recharge": 21},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            {
                "id": "prep_the_subject",
                "name": "Prep The Subject",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 130% ATK damage and make the target take "
                               "16% more damage. Stacks up to 4 times.",
                "effect": {"kind": "apply_vulnerability_stack",
                           "damage_percent": 130, "damage_stat": "attack",
                           "vulnerable_damage_stat": "attack",
                           "percent_per_stack": 16, "max_stacks": 4},
            },
            {
                "id": "begin_the_procedure",
                "name": "Begin The Procedure",
                "min_rarity": "legendary",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 140% ATK damage, increased by 45% for every "
                               "affliction already on the target.",
                "effect": {"kind": "damage_per_affliction", "damage_percent": 140,
                           "bonus_per_affliction": 45, "damage_stat": "attack"},
            },
        ],
        "ultimate_ability": {
            "id": "close_the_theatre",
            "name": "Close The Theatre",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal damage equal to 13% of the target's maximum HP. "
                           "Armour does not reduce it.",
            "effect": {"kind": "true_damage_percent_max_hp", "percent": 13},
        },
    },
    {
        "name": "Iteration Zero",
        "role": "boss",
        "region_roles": {OCELLIOS: "regular"},
        "base_stats": {"attack": 46, "defense": 27, "elemental": 34, "speed": 23,
                       "max_hp": 1520, "max_mana": 999, "crit_rate": 13,
                       "crit_damage": 178, "recharge": 22},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            {
                "id": "the_first_success",
                "name": "The First Success",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 155% ELE damage. If it kills, act again "
                               "immediately.",
                "effect": {"kind": "damage_and_extra_turn_on_kill",
                           "damage_percent": 155, "damage_stat": "elemental"},
            },
            {
                "id": "everything_after",
                "name": "Everything After",
                "min_rarity": "legendary",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 125% ATK damage — 230% if the target is "
                               "above 60% HP.",
                "effect": {"kind": "damage_bonus_if_target_healthy",
                           "damage_percent": 125, "bonus_damage_percent": 105,
                           "hp_threshold_percent": 60, "damage_stat": "attack"},
            },
        ],
        "ultimate_ability": {
            "id": "no_further_revisions",
            "name": "No Further Revisions",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal 195% ATK damage to every enemy, +55% for each "
                           "enemy still standing.",
            "effect": {"kind": "damage_scales_with_enemy_count",
                       "damage_percent": 195, "bonus_per_enemy": 55,
                       "damage_stat": "attack"},
        },
    },
    {
        # THE HARDEST SINGLE ENCOUNTER IN THE GAME, and the one the whole
        # story has been walking toward.
        #
        # Stubby founded Ocellios, invented Void-matter synthesis, and
        # built the mechs that were hacked hostile on the night the
        # Player woke up in this building. "Stubby's Failsafe" is already
        # an Abyssnia elite -- the thing he left running while he was
        # elsewhere. This is not the failsafe.
        #
        # TWO ACTIONS A CYCLE, AND IT WAS THREE. That is the whole tuning
        # story and it is worth keeping, because "the ultimate challenge"
        # is one line of reasoning away from "nobody can finish this".
        #
        # First draft: three actions, 54 attack, 2,600 HP. check_final_
        # bosses measured it at 8% against a full-health reference squad
        # at level 100 -- under its 15% floor, and it said so plainly:
        # "Nobody can finish this region." Brutal is the brief; a wall is
        # not, and a region nobody clears is content nobody sees.
        #
        #     apc 3 / atk 54 / 2600    8% full,  0% at 60%   unbeatable
        #     apc 3 / atk 44 / 2600   21% full,  8% at 60%   still a wall
        #     apc 2 / atk 46 / 2400   42% full, 17% at 60%
        #     apc 2 / atk 52 / 2550   42% full,  4% at 60%   <- here
        #
        # The third action was the problem, not the numbers -- dropping
        # it moved the fight further than a 10-point attack cut did.
        #
        # 42% / 4% is the hardest finale in the game on both axes (The
        # Process, the previous hardest, is 58% / 25%), and the gap
        # between the two columns is the point: Stubby is winnable if you
        # arrive whole and essentially not if you do not. The rest of the
        # region exists to make sure you do not.
        #
        # Levelled at -20 from a squad of 100 per the region config,
        # between Entrospire's -24 and Abyssnia's -16.
        "name": "Stubby",
        "role": "boss",
        "region_roles": {OCELLIOS: "final"},
        "base_stats": {"attack": 52, "defense": 34, "elemental": 40, "speed": 27,
                       "max_hp": 2550, "max_mana": 999, "crit_rate": 14,
                       "crit_damage": 184, "recharge": 24},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            {
                "id": "i_built_all_of_this",
                "name": "I Built All Of This",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 140% ATK damage and make the target take "
                               "18% more damage. Stacks up to 4 times.",
                "effect": {"kind": "apply_vulnerability_stack",
                           "damage_percent": 140, "damage_stat": "attack",
                           "vulnerable_damage_stat": "attack",
                           "percent_per_stack": 18, "max_stacks": 4},
            },
            {
                "id": "including_you",
                "name": "Including You",
                "min_rarity": "legendary",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 160% ELE damage. If it kills, act again "
                               "immediately.",
                "effect": {"kind": "damage_and_extra_turn_on_kill",
                           "damage_percent": 160, "damage_stat": "elemental"},
            },
            {
                "id": "sit_down",
                "name": "Sit Down",
                "min_rarity": "legendary",
                "resource_cost": 34, "resource_type": "mana", "cooldown": 3,
                "description": "Strike the whole squad's poise for 9 and shred "
                               "3 more.",
                "effect": {"kind": "team_poise_strike", "poise_damage": 9,
                           "poise_shred": 3},
            },
        ],
        "ultimate_ability": {
            "id": "the_experiment_concludes",
            "name": "The Experiment Concludes",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal 230% ATK damage to every enemy, increased by 50% "
                           "for every affliction already on the target.",
            "effect": {"kind": "damage_per_affliction", "damage_percent": 230,
                       "bonus_per_affliction": 50, "damage_stat": "attack"},
        },
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "predators_tally")],
    },
]


OCELLIOS_SHORT_NAMES: dict[str, str] = {
    "Subject 14": "Subj. 14",
    "Vivisection Rig": "Vivisection",
    "The Waking Ward": "Waking Ward",
    "Containment Breach": "Breach",
    "Ocellios Orderly": "Orderly",
    "Discarded Iteration": "Discarded",
    "Grafting Bench": "Grafting",
    "Subject 03": "Subj. 03",
    "The Long Experiment": "Experiment",
    "Void Synthesis Core": "Synth Core",
    "Theatre Prime": "Theatre",
    "Iteration Zero": "Iter. Zero",
    "Stubby": "Stubby",
}

OCELLIOS_EMOJI: dict[str, str] = {
    "Subject 14": "🧬",
    "Vivisection Rig": "🔪",
    "The Waking Ward": "🛌",
    "Containment Breach": "🚨",
    "Ocellios Orderly": "🥼",
    "Discarded Iteration": "🗑️",
    "Grafting Bench": "🪡",
    "Subject 03": "🩻",
    "The Long Experiment": "⏱️",
    "Void Synthesis Core": "⚗️",
    "Theatre Prime": "🏥",
    "Iteration Zero": "0️⃣",
    "Stubby": "🎓",
}
