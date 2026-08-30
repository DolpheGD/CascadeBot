"""
The Voidlands's enemy roster.

A SEPARATE MODULE, NOT MORE OF enemies.py. That file is 3,500 lines and
has twice been damaged by scripted edits in the middle of it -- once
losing ~140 lines including `short_name_for` and `BOSS_GROUPS`. A new
region is a self-contained block of content with no reason to be spliced
into the middle of the old one, so it gets its own file and enemies.py
extends its list from here. Nothing about the data format changes.

WHAT THE REGION IS. The ground past Voidcrest where the desert stops
being a desert. Whatever the Void is doing out here it has been doing for
a long time, and it does not destroy things so much as slowly agree that
they were never there. The things still standing in it are the ones that
have refused so far.

WHY IT SITS NEXT TO VOIDCREST DESERT. Deliberately the same thread one
step further along -- Voidcrest is where the Void has touched the land,
the Voidlands are where it has finished. That is also why the roster
below can share enemies with Voidcrest and Abyssnia without either
feeling wrong: it is the middle of a corridor, not an unrelated place.

DESIGN RULE FOR THIS ROSTER: every template is built around PRESSURE --
mechanics that punish standing still, stacking, or letting a fight run
long. That is the mechanical gap between Voidcrest (burst and swarm) and
Abyssnia (raw stat walls). Concretely, the roster leans on:

  * damage that scales with how long the fight has gone (ramp)
  * damage that scales with how many enemies are still up, so killing
    order matters
  * vulnerability stacking, so the danger compounds if ignored
  * true damage, which armour cannot answer

None of these are new engine features -- all four kinds already exist and
are used elsewhere. What is new is a region where all four appear
together, so the answer that carried a player through Voidcrest (out-burst
it) stops working and they have to learn to prioritise.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Stat scale
# ----------------------------------------------------------------------
#
# Interpolated between Voidcrest's and Abyssnia's rosters rather than
# invented. A combat enemy here sits about 20% above a Voidcrest one and
# well under an Abyssnia one, which matches the region's place on the
# expected_squad_level ladder (52 -> 61 -> 70).
#
# level_scale_percent stays at 4 across the board, as everywhere else --
# it is the shared curve, and a region that quietly used 5 would diverge
# from every other region at high floors for no stated reason.

VOIDLANDS_ENEMIES: list[dict] = [
    # ------------------------------------------------------------------
    # COMBAT
    # ------------------------------------------------------------------
    {
        "name": "Void Splinter",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 20, "defense": 11, "elemental": 6, "speed": 12,
                       "max_hp": 78, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 17},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "void_delivery",
            "name": "Errand Of Absence",
            "min_rarity": "common",
            "resource_cost": 20, "resource_type": "mana", "cooldown": 2,
            "description": "Deal 120% ATK damage, +40% for each other enemy still standing.",
            "effect": {"kind": "damage_scales_with_enemy_count",
                       "damage_percent": 120, "bonus_per_enemy": 40,
                       "damage_stat": "attack"},
        }],
    },
    {
        "name": "Unmaking Wisp",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 18, "defense": 14, "elemental": 9, "speed": 9,
                       "max_hp": 92, "max_mana": 999, "crit_rate": 5,
                       "crit_damage": 150, "recharge": 15},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "erosion_mark",
            "name": "Erosion",
            "min_rarity": "common",
            "resource_cost": 22, "resource_type": "mana", "cooldown": 2,
            "description": "Deal 95% ATK damage and make the target take 12% more "
                           "damage. Stacks up to 4 times.",
            "effect": {"kind": "apply_vulnerability_stack",
                       "damage_percent": 95, "damage_stat": "attack",
                       "vulnerable_damage_stat": "attack",
                       "percent_per_stack": 12, "max_stacks": 4},
        }],
    },
    {
        "name": "Rift Stalker",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 23, "defense": 10, "elemental": 5, "speed": 14,
                       "max_hp": 74, "max_mana": 999, "crit_rate": 10,
                       "crit_damage": 170, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "rift_descent",
            "name": "Descent",
            "min_rarity": "common",
            "resource_cost": 24, "resource_type": "mana", "cooldown": 2,
            "description": "Deal 110% ATK damage, +50% for each consecutive use "
                           "on the SAME target (max 3).",
            "effect": {"kind": "damage_ramp_per_use", "damage_percent": 110,
                       "bonus_per_stack": 50, "max_stacks": 3,
                       "damage_stat": "attack"},
        }],
    },
    {
        "name": "Null Warden",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 17, "defense": 16, "elemental": 8, "speed": 8,
                       "max_hp": 105, "max_mana": 999, "crit_rate": 4,
                       "crit_damage": 150, "recharge": 14},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "hold_the_null",
            "name": "Hold The Null",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Shield every ally for 14% of their max HP and raise "
                           "the team's defense by 18% for 3 turns.",
            "effect": {"kind": "team_shield_and_buff", "shield_percent": 14,
                       "buff_stat": "defense", "buff_percent": 18, "duration": 3},
        }],
    },
    {
        "name": "Echo Of The Lost",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 19, "defense": 12, "elemental": 14, "speed": 11,
                       "max_hp": 84, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "the_unwritten",
            "name": "The Unwritten",
            "min_rarity": "common",
            "resource_cost": 25, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 100% ATK damage to every enemy, with a 45% chance "
                           "to inflict 20% ATK a turn for 3 turns.",
            "effect": {"kind": "aoe_damage_chance_dot", "damage_percent": 100,
                       "damage_stat": "attack", "dot_chance_percent": 45,
                       "dot_stat": "attack", "dot_percent": 20, "duration": 3},
        }],
    },
    {
        "name": "Collapse Herald",
        "role": "combat",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 22, "defense": 15, "elemental": 6, "speed": 10,
                       "max_hp": 98, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 160, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "cast_out",
            "name": "Cast Out",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 125% ATK damage with a 40% chance to stun for 1 turn.",
            "effect": {"kind": "damage_and_stun", "damage_percent": 125,
                       "damage_stat": "attack", "chance_percent": 40, "duration": 1},
        }],
    },

    # ------------------------------------------------------------------
    # ELITE
    # ------------------------------------------------------------------
    {
        "name": "The Gathering Absence",
        "role": "elite",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 27, "defense": 18, "elemental": 12, "speed": 12,
                       "max_hp": 168, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 165, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "gathering",
            "name": "Gathering",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 130% ATK damage, +45% for each other enemy still "
                           "standing.",
            "effect": {"kind": "damage_scales_with_enemy_count",
                       "damage_percent": 130, "bonus_per_enemy": 45,
                       "damage_stat": "attack"},
        }],
        # The reason this elite is dangerous is that it is worth killing
        # FIRST and looks like it should be killed last -- a durable
        # support body whose damage grows with the crowd it is protecting.
        # HEAL, NOT SHIELD, and that is not a flavour choice.
        # _trigger_on_low_hp dispatches exactly two effect kinds --
        # prevent_death and heal_percent_max_hp. This passive was written
        # as self_shield_percent_max_hp, which is a real effect kind and
        # a valid key set, so every check passed and it would simply
        # never have fired. Presence is not effect.
        "passive_abilities": [{
            "id": "refusal_to_end",
            "name": "Refusal To End",
            "min_rarity": "epic",
            "trigger": "on_low_hp",
            "description": "Below 30% HP, recover 22% of max HP. Once per fight.",
            "effect": {"kind": "heal_percent_max_hp", "percent": 22,
                       "hp_threshold_percent": 30},
        }],
    },
    {
        "name": "Entropy Marshal",
        "role": "elite",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 31, "defense": 16, "elemental": 10, "speed": 15,
                       "max_hp": 152, "max_mana": 999, "crit_rate": 12,
                       "crit_damage": 175, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "unmake",
            "name": "Unmake",
            "min_rarity": "epic",
            "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
            "description": "Deal damage equal to 9% of the target's maximum HP. "
                           "Armour does not reduce it.",
            "effect": {"kind": "true_damage_percent_max_hp", "percent": 9},
        }],
    },
    {
        "name": "Archivist Of Unbeing",
        "role": "elite",
        "regions": ["The Voidlands"],
        "base_stats": {"attack": 25, "defense": 17, "elemental": 20, "speed": 11,
                       "max_hp": 160, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 160, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "catalogue_of_absence",
            "name": "Catalogue Of Absence",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 115% ATK damage, increased by 35% for every "
                           "affliction already on the target.",
            "effect": {"kind": "damage_per_affliction", "damage_percent": 115,
                       "bonus_per_affliction": 35, "damage_stat": "attack"},
        }],
    },

    # ------------------------------------------------------------------
    # BOSSES
    # ------------------------------------------------------------------
    {
        "name": "The Hollow Choir",
        "role": "boss",
        "region_roles": {"The Voidlands": "regular"},
        "base_stats": {"attack": 34, "defense": 20, "elemental": 16, "speed": 14,
                       "max_hp": 640, "max_mana": 999, "crit_rate": 10,
                       "crit_damage": 170, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "dissonance",
            "name": "Dissonance",
            "min_rarity": "legendary",
            "resource_cost": 34, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 105% ATK damage to every enemy and make them 14% "
                           "more vulnerable for 3 turns.",
            "effect": {"kind": "aoe_damage_chance_debuff", "damage_percent": 105,
                       "damage_stat": "attack", "debuff_chance_percent": 100,
                       "debuff_stat": "defense", "debuff_percent": -14,
                       "duration": 3},
        }],
        "ultimate_ability": {
            "id": "the_chorus_agrees",
            "name": "The Chorus Agrees",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal 180% ATK damage to every enemy, +55% for each "
                           "enemy still standing.",
            "effect": {"kind": "damage_scales_with_enemy_count",
                       "damage_percent": 180, "bonus_per_enemy": 55,
                       "damage_stat": "attack"},
        },
    },
    {
        "name": "Nullstone Bastion",
        "role": "boss",
        "region_roles": {"The Voidlands": "regular"},
        # A REGULAR boss, and these numbers were briefly not.
        #
        # A scripted regex tuning pass aimed at the region finale below
        # anchored on `"defense": 26`, which this template also had and
        # which appears first in the file -- so the first iteration
        # rewrote THIS boss to 2,000 HP and attack 52, making a regular
        # encounter harder than the region's own finale. Caught by
        # check_progression's boss-spread rule (3.1x against a 2.0x
        # limit), not by reading the diff.
        #
        # Restored to a durable-but-modest regular: 760 against the
        # Sitting Speaker's 640 is a 1.2x spread, so which of the two a
        # run draws is a change of texture rather than of outcome.
        "base_stats": {"attack": 30, "defense": 26, "elemental": 14, "speed": 11,
                       "max_hp": 760, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 165, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "hold_the_stone",
            "name": "Hold The Stone",
            "min_rarity": "legendary",
            "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
            "description": "Taunt every enemy and shield itself for 20% of max HP.",
            "effect": {"kind": "taunt_and_shield", "shield_percent": 20, "duration": 2,
                       "buff_stat": "defense", "buff_percent": 30},
        }],
        "ultimate_ability": {
            "id": "the_void_decides",
            "name": "The Void Decides",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal damage equal to 14% of the target's maximum HP. "
                           "Armour does not reduce it.",
            "effect": {"kind": "true_damage_percent_max_hp", "percent": 14},
        },
    },
    {
        # THE REGION FINALE.
        #
        # Deliberately a PRESSURE boss rather than a stat wall: its
        # threat grows the longer the fight runs, so the fail state is
        # "took too long" instead of "did not hit hard enough". That is
        # the lesson the region is teaching, and it is the one thing
        # Abyssnia's finale (Rohan, a raw wall) does not test.
        #
        # Level delta is -18 per the region config, between Voidcrest's
        # -20 and Abyssnia's -16.
        #
        # STATS SOLVED AGAINST check_final_bosses, not chosen. The first
        # version shipped 1,180 HP and attack 38, which is LESS HP than
        # Boss John (1,780) one region below it -- the check called it
        # "a formality" at a 100% clear rate from 60% health. Four passes:
        #
        #     atk 38 / hp 1180   100% full, 100% at 60%   a formality
        #     atk 48 / hp 1950    88% / 46%               softer than Voidcrest
        #     atk 58 / hp 2050    58% / 25%               as hard as Entrospire
        #     atk 50 / hp 1990    71% / 46%               <- here
        #
        # 71/46 sits between Voidcrest's 79/58 and Abyssnia's 58/42,
        # which is the whole point of a bridge region. Note how sharp the
        # cliff is between attack 50 and 52 (71% -> 58%): this fight is
        # very sensitive to incoming damage, so it is worth re-running
        # the check after any change here rather than reasoning about it.
        "name": "The Unmaking",
        "role": "boss",
        "region_roles": {"The Voidlands": "final"},
        "base_stats": {"attack": 50, "defense": 27, "elemental": 31, "speed": 27,
                       "max_hp": 1990, "max_mana": 999, "crit_rate": 12,
                       "crit_damage": 180, "recharge": 22},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            {
                "id": "reading_of_the_absent",
                "name": "Reading Of The Absent",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 120% ATK damage and make the target take 15% more "
                               "damage. Stacks up to 4 times.",
                "effect": {"kind": "apply_vulnerability_stack",
                           "damage_percent": 120, "damage_stat": "attack",
                           "vulnerable_damage_stat": "attack",
                           "percent_per_stack": 15, "max_stacks": 4},
            },
            {
                "id": "the_gap_widens",
                "name": "The Gap Widens",
                "min_rarity": "legendary",
                "resource_cost": 34, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 135% ATK damage, increased by 40% for every "
                               "affliction already on the target.",
                "effect": {"kind": "damage_per_affliction", "damage_percent": 135,
                           "bonus_per_affliction": 40, "damage_stat": "attack"},
            },
        ],
        "ultimate_ability": {
            "id": "cessation",
            "name": "Cessation Without End",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal 210% ATK damage to every enemy, +60% for each "
                           "consecutive use.",
            "effect": {"kind": "damage_ramp_per_use", "damage_percent": 210,
                       "bonus_per_stack": 60, "max_stacks": 4,
                       "damage_stat": "attack"},
        },
    },
]

# Short names for the combat log, same contract as enemies.ENEMY_SHORT_NAMES.
VOIDLANDS_SHORT_NAMES: dict[str, str] = {
    "Void Splinter": "Splinter",
    "Unmaking Wisp": "Wisp",
    # "Stalker" was already taken by Duneglass Stalker, and short names
    # are how the combat log tells two enemies apart -- two "Stalker"
    # lines in one fight is a log nobody can follow. Caught by
    # check_ui_labels, which is the only thing that would have.
    "Rift Stalker": "Rift",
    "Null Warden": "Warden",
    "Echo Of The Lost": "Echo",
    "Collapse Herald": "Herald",
    "The Gathering Absence": "Absence",
    "Entropy Marshal": "Marshal",
    "Archivist Of Unbeing": "Archivist",
    "The Hollow Choir": "Choir",
    "Nullstone Bastion": "Nullstone",
    "The Unmaking": "Unmaking",
}
