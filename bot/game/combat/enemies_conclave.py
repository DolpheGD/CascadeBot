"""
The Conclave: enemy SUPPORT that actually supports.

THE GAP THIS FILLS. After the specialists pass, ten effect kinds were
still enemy-unused, and eight of them turned out to be the same kind of
thing: TEAM buffs. team_double_buff, team_heal_and_buff,
team_buff_and_resource, team_break_and_poise_buff, team_heal_from_stat,
team_poise_strike -- the enemy roster had almost no equivalent of the
player's Amplifier and Sustain classes, so an enemy lineup was a pile of
attackers and the only question was which to hit first.

That is the difference between a fight and a queue. A player squad is
built as a SYSTEM -- a carry, somebody making it hit harder, somebody
keeping it alive -- and until now nothing on the other side was. These
templates give enemy groups the same shape, which changes the basic
question of a fight from "who has the least HP" to "what is holding this
lineup together".

WHY THAT IS HARD WITHOUT BEING UNFAIR. Every one of these is fragile.
They have low HP and poor defence for their tier on purpose: the counter
is always available and always the same -- find the support, kill it
first -- so the difficulty is in RECOGNISING the threat rather than in
out-statting it. An enemy that buffs its team and is also the tankiest
thing in the room would just be a wall.

THE ONE EXCEPTION, and it is deliberate. Chorus Of The Last Shift spends
75% of its own health to hand its team poise armour. It is designed to be
killed and to not care, because a support that dies having already paid
out is a genuinely different problem from one you can silence.
"""

from __future__ import annotations

from bot.game.loot.abilities import ARMOR_PASSIVES, get_ability_by_id

GLACIER = "Glacier 15"
WASTELANDS = "The Wastelands"
HOTLANDS = "The Hotlands"
VOIDCREST = "Voidcrest Desert"
VOIDLANDS = "The Voidlands"
ABYSSNIA = "Abyssnia"
DEEPWORKS = "Entrospire Deepworks"


CONCLAVE_ENEMIES: list[dict] = [
    # ==================================================================
    # COMBAT -- fragile support, available early
    # ==================================================================
    {
        # THE FIRST ENEMY AMPLIFIER a player meets, and deliberately in
        # the second region rather than the fifth. "Kill the support
        # first" is a habit worth teaching while the fights are still
        # survivable enough to learn it in.
        "name": "Signal Chorister",
        "role": "combat",
        "regions": [WASTELANDS, HOTLANDS, VOIDCREST],
        "base_stats": {"attack": 13, "defense": 8, "elemental": 11, "speed": 15,
                       "max_hp": 58, "max_mana": 999, "crit_rate": 5,
                       "crit_damage": 150, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "raise_the_pitch",
            "name": "Raise The Pitch",
            "min_rarity": "common",
            "resource_cost": 22, "resource_type": "mana", "cooldown": 3,
            "description": "Raise the crew's crit rate by 22% and crit damage by "
                           "30% for 3 turns.",
            "effect": {"kind": "team_double_buff",
                       "buff_stat_1": "crit_rate", "buff_percent_1": 22,
                       "buff_stat_2": "crit_damage", "buff_percent_2": 30,
                       "duration": 3},
        }],
    },
    {
        # ENEMY SUSTAIN. Heals AND buffs defence in one action, so
        # ignoring it costs twice.
        "name": "Triage Warden",
        "role": "combat",
        "regions": [HOTLANDS, VOIDCREST, VOIDLANDS, ABYSSNIA],
        "base_stats": {"attack": 15, "defense": 12, "elemental": 13, "speed": 12,
                       "max_hp": 74, "max_mana": 999, "crit_rate": 4,
                       "crit_damage": 150, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "hold_them_together",
            "name": "Hold Them Together",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Heal the crew for 26% of their max HP and raise their "
                           "defense by 30% for 3 turns.",
            "effect": {"kind": "team_heal_and_buff", "heal_percent": 26,
                       "buff_stat": "defense", "buff_percent": 30, "duration": 3},
        }],
    },
    {
        # RESOURCE SUPPORT -- pushes the whole lineup's ultimates forward.
        # The threat is not this turn, it is that everything else acts
        # sooner than it should.
        "name": "Powder Runner",
        "role": "combat",
        "regions": [WASTELANDS, HOTLANDS, DEEPWORKS],
        "base_stats": {"attack": 16, "defense": 9, "elemental": 9, "speed": 17,
                       "max_hp": 62, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 155, "recharge": 21},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "hand_it_forward",
            "name": "Hand It Forward",
            "min_rarity": "common",
            "resource_cost": 24, "resource_type": "mana", "cooldown": 3,
            "description": "Raise the crew's attack by 20% for 3 turns and give "
                           "them 10 energy and 12 mana.",
            "effect": {"kind": "team_buff_and_resource", "buff_stat": "attack",
                       "buff_percent": 20, "duration": 3,
                       "energy_amount": 10, "mana_amount": 12},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "steady_cadence")],
    },
    {
        # POISE NUKE. Strips the squad's poise directly rather than
        # buffing somebody else to do it -- the fastest route from "fine"
        # to "everybody is Broken" in the game.
        "name": "Hammerfall Crew",
        "role": "combat",
        "regions": [VOIDCREST, VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 19, "defense": 14, "elemental": 7, "speed": 11,
                       "max_hp": 96, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "all_at_once",
            "name": "All At Once",
            "min_rarity": "common",
            "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
            "description": "Strike the whole squad's poise for 8 and shred 2 more.",
            "effect": {"kind": "team_poise_strike", "poise_damage": 8,
                       "poise_shred": 2},
        }],
    },
    {
        # SELF-HARM DOT. Pays its own HP for a spreading burn, so it gets
        # more dangerous as it dies -- and healing it is not an option
        # its own team has.
        "name": "Kindling Martyr",
        "role": "combat",
        "regions": [HOTLANDS, VOIDLANDS, ABYSSNIA],
        "base_stats": {"attack": 17, "defense": 10, "elemental": 20, "speed": 13,
                       "max_hp": 90, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 160, "recharge": 17},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "give_it_all_up",
            "name": "Give It All Up",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Spend 11% of its own HP for 85% ELE damage, 25% "
                           "splash, and a burn for 4 turns.",
            "effect": {"kind": "sacrifice_hp_damage_and_dot", "self_cost_percent": 11,
                       "damage_percent": 85, "damage_stat": "elemental",
                       "splash_percent": 25, "dot_stat": "elemental",
                       "dot_percent": 48, "hp_scaling": 2.6, "duration": 4},
        }],
    },

    # ==================================================================
    # ELITE
    # ==================================================================
    {
        # BREAK ENABLER. Makes the whole lineup better at breaking the
        # squad AND better at punishing it once broken -- the pair of
        # things Shear Foreman and Deepworks Regulator do separately.
        "name": "Faultline Conductor",
        "role": "elite",
        "regions": [VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 25, "defense": 15, "elemental": 18, "speed": 14,
                       "max_hp": 148, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 162, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "find_the_fault",
            "name": "Find The Fault",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "For 3 turns the crew deals 70% more damage to Broken "
                           "targets and chips 2 extra poise.",
            "effect": {"kind": "team_break_and_poise_buff", "break_percent": 70,
                       "poise_amount": 2, "duration": 3},
        }],
    },
    {
        # HEALS OFF ITS OWN ELEMENTAL. Scales with a stat the squad
        # cannot reduce by killing its allies, so the only answer is to
        # kill IT -- and it is soft enough that the answer works.
        "name": "Wellspring Adept",
        "role": "elite",
        "regions": [VOIDCREST, VOIDLANDS, ABYSSNIA],
        "base_stats": {"attack": 20, "defense": 14, "elemental": 26, "speed": 13,
                       "max_hp": 138, "max_mana": 999, "crit_rate": 5,
                       "crit_damage": 155, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "draw_from_the_well",
            "name": "Draw From The Well",
            "min_rarity": "epic",
            "resource_cost": 32, "resource_type": "mana", "cooldown": 4,
            "description": "Heal the whole crew, scaling off its Elemental.",
            "effect": {"kind": "team_heal_from_stat", "stat": "elemental",
                       "percent": 620},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "medics_covenant")],
    },
    {
        # THE MARTYR. Spends three quarters of its own health to give the
        # crew poise armour, and is meant to die having already paid.
        # Silencing it is not possible; the only counter is to kill it
        # BEFORE it acts, which makes turn order the puzzle.
        "name": "Chorus Of The Last Shift",
        "role": "elite",
        "regions": [ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 23, "defense": 18, "elemental": 15, "speed": 10,
                       "max_hp": 210, "max_mana": 999, "crit_rate": 5,
                       "crit_damage": 152, "recharge": 17},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "spend_the_shift",
            "name": "Spend The Shift",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 5,
            "description": "Burn 70% of its own HP to armour the crew's poise "
                           "for 2 turns.",
            "effect": {"kind": "sacrifice_hp_team_poise_buff", "self_cost_percent": 70,
                       "hp_per_point": 180, "duration": 2},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "last_ward")],
    },

    # ==================================================================
    # BOSS
    # ==================================================================
    {
        # A BOSS THAT IS ITS OWN SUPPORT, which no other boss is. Buffs
        # the crowd, heals the crowd, and hits -- so a lineup built
        # around it is genuinely harder than the sum of its bodies, and
        # the usual "focus the boss" answer is correct for once.
        #
        # Placed in the Hotlands, which had seven bosses but none that
        # changed how its escorts behaved.
        "name": "The Standing Ovation",
        "role": "boss",
        "region_roles": {HOTLANDS: "regular", VOIDCREST: "regular"},
        # HP SET BY THE SMALLEST BOSS IN ITS WEAKEST REGION, not by what
        # the fight wants. It is a regular in both the Hotlands and
        # Voidcrest, and the Hotlands' floor is Samuel at 265 -- so 590
        # made that region's boss spread 2.2x, over check_progression's
        # 2.0x rule, and which boss a run drew would have decided it.
        # 525 sits just under Samuel's double and alongside Boss John's
        # Driller Prototype at 520.
        #
        # Costs nothing that matters. This boss is dangerous because it
        # buffs and heals the lineup around it, not because of its own
        # health bar; a bigger bar would have made it longer, not harder.
        "base_stats": {"attack": 30, "defense": 19, "elemental": 24, "speed": 18,
                       "max_hp": 525, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 168, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "encore",
                "name": "Encore",
                "min_rarity": "legendary",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Raise the crew's attack by 26% and speed by 20% "
                               "for 3 turns.",
                "effect": {"kind": "team_double_buff",
                           "buff_stat_1": "attack", "buff_percent_1": 26,
                           "buff_stat_2": "speed", "buff_percent_2": 20,
                           "duration": 3},
            },
            {
                "id": "take_a_bow",
                "name": "Take A Bow",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 4,
                "description": "Heal the crew for 30% of their max HP and raise "
                               "their defense by 34% for 3 turns.",
                "effect": {"kind": "team_heal_and_buff", "heal_percent": 30,
                           "buff_stat": "defense", "buff_percent": 34,
                           "duration": 3},
            },
        ],
        "ultimate_ability": {
            "id": "the_whole_house",
            "name": "The Whole House",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Deal 165% ATK damage to every enemy, +50% for each "
                           "enemy still standing.",
            "effect": {"kind": "damage_scales_with_enemy_count",
                       "damage_percent": 165, "bonus_per_enemy": 50,
                       "damage_stat": "attack"},
        },
    },
]

CONCLAVE_SHORT_NAMES: dict[str, str] = {
    "Signal Chorister": "Chorister",
    "Triage Warden": "Triage",
    "Powder Runner": "Runner",
    "Hammerfall Crew": "Hammerfall",
    "Kindling Martyr": "Kindling",
    "Faultline Conductor": "Faultline",
    "Wellspring Adept": "Wellspring",
    "Chorus Of The Last Shift": "Last Shift",
    "The Standing Ovation": "Ovation",
}

CONCLAVE_EMOJI: dict[str, str] = {
    "Signal Chorister": "🎵",
    "Triage Warden": "⛑️",
    "Powder Runner": "🏃",
    "Hammerfall Crew": "🔨",
    "Kindling Martyr": "🕯️",
    "Faultline Conductor": "🪓",
    "Wellspring Adept": "⛲",
    "Chorus Of The Last Shift": "🔔",
    "The Standing Ovation": "👏",
}
