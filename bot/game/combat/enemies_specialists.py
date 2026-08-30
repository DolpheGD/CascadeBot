"""
Specialists: enemies built around mechanics no enemy in the game used.

WHY THIS EXISTS AND WHAT IT IS NOT. It is not "more enemies". The roster
already had 160 templates and adding a 161st that deals damage and
sometimes stuns would have made the lineups longer without making them
different -- which is the failure mode this project has hit before and
explicitly does not want repeated.

The starting point was an audit, not an idea. Of the 70 effect kinds the
engine implements, enemies used 48. Twenty-two had never appeared on an
enemy in the game's history, and twenty-two of the fifty-eight ARMOR
passives were likewise enemy-unused. That list IS the design brief: every
template below is built on something from it.

WHAT MAKES THESE HARD, and it is deliberately not bigger numbers. Each
one invalidates a habit that works everywhere else:

    Slagjaw Breaker      banks a shield, then spends it for huge damage
    The Full Measure     hits HARDEST at full HP, inverting execute
    Cascade Failure      gets an extra turn on every kill it lands
    Sanitation Unit 9    strips your debuffs and shields its own team
    Choir Of Small Debts the enemy team heals off the damage it deals
    Overpressure Cell    burns its own HP to race you
    Bulwark Shift        taunts AND shields the enemy backline
    Ranging Officer      calls a strike that lands in two turns
    Shear Foreman        breaks your squad's poise far faster
    The Opportunist      hits far harder into an ally you let break

A squad that beats all ten the same way does not exist: sitting at full
HP loses to the second, letting anything die loses to the third, debuff
comps lose to the fourth, and slow attrition loses to the fifth. That is
what "diverse lineups" has to mean to be worth anything.

ONE OF THESE WAS WRONG ON THE FIRST PASS AND IS WORTH RECORDING. Slagjaw
Breaker and The Long Arrears were written as ANTI-SHIELD -- punishing the
player for stacking shields -- on the assumption that
`damage_consumes_shield` read the target's shield pool. It reads the
ATTACKER's. Both abilities were therefore describing something the engine
does not do, and every check passed: the effect kind was real, the keys
were real, the numbers were sane. It took running the ability against a
shielded and an unshielded dummy and seeing IDENTICAL damage to find it.
Both are now built on what the effect actually does, and the pairing with
Bulwark Shift (which shields the whole enemy crew) is a better lineup
than the one I was trying to fake.

WHERE THEY GO. Weighted at ENTROSPIRE DEEPWORKS, which was the thinnest
region in the game -- 9 combat, 6 elite and 2 bosses, for the ENDGAME
tier, against Glacier 15's 23/12/5. The rest spread across the mid and
late regions so the lineups there stop being predictable. Placement is
per-template rather than by rule, because these are pointed enough that
"everything in region X" would put a shield-punisher in front of a player
who has not been taught shields yet.

A SEPARATE MODULE for the same reason as enemies_voidlands.py: enemies.py
is 3,500 lines and scripted edits into the middle of it have destroyed
working code twice in this project's history.
"""

from __future__ import annotations

from bot.game.loot.abilities import ARMOR_PASSIVES, get_ability_by_id

# Region name constants -- typos here are silent, since an unknown region
# name simply means the template never spawns anywhere.
GLACIER = "Glacier 15"
WASTELANDS = "The Wastelands"
HOTLANDS = "The Hotlands"
VOIDCREST = "Voidcrest Desert"
VOIDLANDS = "The Voidlands"
ABYSSNIA = "Abyssnia"
DEEPWORKS = "Entrospire Deepworks"


SPECIALIST_ENEMIES: list[dict] = [
    # ==================================================================
    # COMBAT
    # ==================================================================
    {
        # A SHIELD BATTERY, NOT AN ANTI-SHIELD -- and the first draft of
        # this template had it exactly backwards.
        #
        # `damage_consumes_shield` reads the ATTACKER's own shield pool
        # and converts it to damage. It was written for Jofrog and Bee
        # Jee, to give a shielder somebody worth shielding. I wrote this
        # enemy as a punisher of the player's shields and gave it a
        # description saying so; probing it in a real fight showed
        # identical damage against a shielded and an unshielded target,
        # because the target's shield was never part of the sum.
        #
        # Every check passed. The effect kind was real, the keys were
        # real, the numbers were sane -- and the ability did something
        # other than what it said, which is the one thing this project
        # treats as non-negotiable.
        #
        # Rebuilt around what the effect ACTUALLY does, which turns out
        # to be more interesting than the thing I was trying to fake: it
        # shields itself, then spends the shield to hit far harder. The
        # counterplay is to make it spend the shield early on somebody
        # who can take it, and the danger is letting it stack with a
        # Bulwark Shift or an Understudy Medic in the same lineup -- both
        # of which share three regions with it.
        "name": "Slagjaw Breaker",
        "role": "combat",
        "regions": [HOTLANDS, VOIDCREST, VOIDLANDS, DEEPWORKS],
        "base_stats": {"attack": 21, "defense": 12, "elemental": 7, "speed": 11,
                       "max_hp": 88, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 160, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "bank_the_plate",
                "name": "Bank The Plate",
                "min_rarity": "common",
                "resource_cost": 20, "resource_type": "mana", "cooldown": 3,
                "description": "Shield itself for 26% of its max HP.",
                "effect": {"kind": "self_shield_percent_max_hp", "percent": 26},
            },
            {
                "id": "discharge_the_plate",
                "name": "Discharge The Plate",
                "min_rarity": "common",
                "resource_cost": 24, "resource_type": "mana", "cooldown": 2,
                "description": "Spend all of its own shielding to deal 130% ATK "
                               "damage plus more for every point spent.",
                "effect": {"kind": "damage_consumes_shield", "damage_percent": 130,
                           "percent_per_shield": 0.4, "max_bonus_percent": 240,
                           "damage_stat": "attack"},
            },
        ],
    },
    {
        # SELF-HARMING NUKER. Races you: its damage scales with the HP it
        # spends, so it is most dangerous at the start of a fight and
        # least at the end -- the inverse of every ramping enemy. Killing
        # it slowly is correct, which is not a sentence that applies to
        # anything else in the roster.
        "name": "Overpressure Cell",
        "role": "combat",
        "regions": [HOTLANDS, VOIDLANDS, DEEPWORKS],
        "base_stats": {"attack": 24, "defense": 9, "elemental": 15, "speed": 13,
                       "max_hp": 104, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "vent_everything",
            "name": "Vent Everything",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 3,
            "description": "Spend 14% of its own HP to hit the whole squad, "
                           "harder the more it spent.",
            "effect": {"kind": "sacrifice_hp_aoe_damage", "self_cost_percent": 14,
                       "damage_percent": 65, "damage_stat": "attack",
                       "hp_scaling": 240},
        }],
    },
    {
        # PUNISHES A BROKEN ALLY. Break is a system the player uses on
        # enemies and has never had used against them with any weight.
        "name": "The Opportunist",
        "role": "combat",
        "regions": [VOIDCREST, VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 23, "defense": 11, "elemental": 8, "speed": 16,
                       "max_hp": 82, "max_mana": 999, "crit_rate": 11,
                       "crit_damage": 175, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "find_the_seam",
            "name": "Find The Seam",
            "min_rarity": "common",
            "resource_cost": 22, "resource_type": "mana", "cooldown": 2,
            "description": "Deal 95% ATK damage — 210% against a Broken target, "
                           "splashing 25% onto the rest of the squad.",
            "effect": {"kind": "damage_bonus_if_target_broken", "damage_percent": 95,
                       "bonus_damage_percent": 115, "damage_stat": "attack",
                       "splash_percent": 25},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "shatterpoint_focus")],
    },
    {
        # POISE PRESSURE. Makes the whole enemy side break the squad
        # faster -- the player's own break mechanic, aimed the other way.
        "name": "Shear Foreman",
        "role": "combat",
        "regions": [ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 20, "defense": 16, "elemental": 10, "speed": 10,
                       "max_hp": 112, "max_mana": 999, "crit_rate": 5,
                       "crit_damage": 150, "recharge": 15},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "work_the_joints",
            "name": "Work The Joints",
            "min_rarity": "common",
            "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
            "description": "The whole crew chips 2 extra poise for 3 turns, and "
                           "splash 55% of their damage.",
            "effect": {"kind": "team_poise_damage_buff", "amount": 2, "duration": 3,
                       "splash_percent": 55, "damage_stat": "attack"},
        }],
    },
    {
        # TELEGRAPHED AOE. A timer, which nothing else in the roster is:
        # the strike lands in two turns whether or not the spotter is
        # alive, so the decision is "kill it now or survive it later".
        "name": "Ranging Officer",
        "role": "combat",
        "regions": [WASTELANDS, HOTLANDS, VOIDCREST, DEEPWORKS],
        "base_stats": {"attack": 18, "defense": 10, "elemental": 12, "speed": 14,
                       "max_hp": 76, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "mark_for_fire",
            "name": "Mark For Fire",
            "min_rarity": "common",
            "resource_cost": 26, "resource_type": "mana", "cooldown": 4,
            "description": "Deal 55% ATK damage to the squad and call a strike "
                           "that lands for 175% in 2 turns.",
            "effect": {"kind": "aoe_call_in_strike", "damage_percent": 55,
                       "damage_stat": "attack", "strike_percent": 175,
                       "delay_turns": 2},
        }],
    },
    {
        # ENEMY HEALER that scales off its own max HP rather than a
        # damage stat, so killing the bruisers first does not shrink its
        # output. The answer is to kill the healer, which is the lesson.
        "name": "Understudy Medic",
        "role": "combat",
        "regions": [WASTELANDS, HOTLANDS, VOIDLANDS, DEEPWORKS],
        "base_stats": {"attack": 14, "defense": 15, "elemental": 9, "speed": 12,
                       "max_hp": 120, "max_mana": 999, "crit_rate": 4,
                       "crit_damage": 150, "recharge": 17},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "field_stitching",
            "name": "Field Stitching",
            "min_rarity": "common",
            "resource_cost": 24, "resource_type": "mana", "cooldown": 3,
            "description": "Heal the most wounded ally for 34% of its own max HP.",
            "effect": {"kind": "heal_from_stat", "stat": "max_hp", "percent": 34},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "steady_cadence")],
    },

    # ==================================================================
    # ELITE
    # ==================================================================
    {
        # INVERTED EXECUTE. Everything in the game rewards being topped
        # up; this hits 185% into a healthy target and 105% into a hurt
        # one. Healing to full in front of it is the wrong move, and no
        # other enemy has ever made "stay at 55%" the right answer.
        "name": "The Full Measure",
        "role": "elite",
        "regions": [VOIDCREST, VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 29, "defense": 17, "elemental": 13, "speed": 13,
                       "max_hp": 158, "max_mana": 999, "crit_rate": 9,
                       "crit_damage": 168, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "full_measure",
            "name": "Full Measure",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "Deal 105% ATK damage — 185% if the target is above "
                           "60% HP.",
            "effect": {"kind": "damage_bonus_if_target_healthy",
                       "damage_percent": 105, "bonus_damage_percent": 80,
                       "hp_threshold_percent": 60, "damage_stat": "attack"},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "honed_grip")],
    },
    {
        # ANTI-DEBUFF. Strips what the squad spent turns applying and
        # shields its team for doing it. Debuff-stacking comps are a
        # real strategy with no counterplay in the roster until now.
        "name": "Sanitation Unit 9",
        "role": "elite",
        "regions": [VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 24, "defense": 21, "elemental": 16, "speed": 12,
                       "max_hp": 176, "max_mana": 999, "crit_rate": 6,
                       "crit_damage": 155, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "purge_cycle",
            "name": "Purge Cycle",
            "min_rarity": "epic",
            "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
            "description": "Clear every debuff from its crew and shield them all "
                           "for 30% of their max HP.",
            "effect": {"kind": "team_shield_and_cleanse", "shield_percent": 30},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "purifiers_censer")],
    },
    {
        # SUSTAIN RACE. The enemy side heals off the damage it deals, so
        # a slow grind loses outright and the fight becomes a burst
        # check. Nothing else in the roster forces that.
        "name": "Choir Of Small Debts",
        "role": "elite",
        "regions": [VOIDLANDS, ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 27, "defense": 16, "elemental": 21, "speed": 14,
                       "max_hp": 164, "max_mana": 999, "crit_rate": 8,
                       "crit_damage": 165, "recharge": 20},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "collect_in_kind",
            "name": "Collect In Kind",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 4,
            "description": "For 4 turns the whole crew heals for 38% of the "
                           "damage they deal.",
            "effect": {"kind": "team_lifesteal_buff", "percent": 38, "duration": 4},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "leeching_barbs")],
    },
    {
        # A REAL GUARDIAN. Taunts AND shields the people behind it, so
        # the backline cannot be reached until it is dealt with -- the
        # protect-the-carry pattern the player uses, finally aimed back.
        "name": "Bulwark Shift",
        "role": "elite",
        "regions": [VOIDCREST, VOIDLANDS, DEEPWORKS],
        "base_stats": {"attack": 22, "defense": 26, "elemental": 10, "speed": 9,
                       "max_hp": 205, "max_mana": 999, "crit_rate": 4,
                       "crit_damage": 150, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "close_ranks",
            "name": "Close Ranks",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "Force every enemy to target it, and shield the whole "
                           "crew for 32% of their max HP, for 3 turns.",
            "effect": {"kind": "taunt_and_team_shield", "shield_percent": 32,
                       "duration": 3},
        }],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "last_ward")],
    },
    {
        # BREAK PAYOFF for the enemy side. Pairs with Shear Foreman and
        # The Opportunist: the three of them together turn poise from a
        # thing the player does into a thing that is done to them.
        "name": "Deepworks Regulator",
        "role": "elite",
        "regions": [ABYSSNIA, DEEPWORKS],
        "base_stats": {"attack": 26, "defense": 19, "elemental": 14, "speed": 12,
                       "max_hp": 170, "max_mana": 999, "crit_rate": 7,
                       "crit_damage": 160, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [{
            "id": "exploit_the_fault",
            "name": "Exploit The Fault",
            "min_rarity": "epic",
            "resource_cost": 30, "resource_type": "mana", "cooldown": 3,
            "description": "For 3 turns the whole crew deals 40% more damage to "
                           "Broken targets.",
            "effect": {"kind": "team_break_damage_buff", "percent": 40,
                       "duration": 3},
        }],
    },

    # ==================================================================
    # BOSSES
    # ==================================================================
    {
        # THE KILL-CHAINER, and the hardest thing in this file.
        #
        # An extra turn on every kill means losing one squad member can
        # lose the fight outright -- it acts, kills, acts again. No other
        # enemy in the game snowballs off a death, and it makes "nobody
        # dies" a real objective rather than a preference.
        #
        # Given to Entrospire, which had two bosses total for the
        # endgame tier and needed a finale-calibre regular.
        "name": "Cascade Failure",
        "role": "boss",
        "region_roles": {DEEPWORKS: "regular"},
        # HP CAPPED BY ITS NEIGHBOUR, not by what the fight wants.
        #
        # First written at 1,450, which check_progression rejected: Floor
        # Manager PRIME is Entrospire's other regular at 640, and a 2.3x
        # spread means which boss the run draws decides it before it
        # starts. 1,250 is the ceiling that rule allows, and the right
        # call is to respect it rather than to raise PRIME -- PRIME is
        # tuned, shipped, and not the thing being added here.
        #
        # The danger lives in the KIT rather than the health bar anyway.
        # An extra turn per kill is what makes this fight frightening;
        # 200 more HP would only have made it longer.
        "base_stats": {"attack": 40, "defense": 24, "elemental": 34, "speed": 24,
                       "max_hp": 1250, "max_mana": 999, "crit_rate": 11,
                       "crit_damage": 175, "recharge": 21},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            {
                "id": "propagate",
                "name": "Propagate",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Deal 150% ELE damage. If it kills, act again "
                               "immediately.",
                "effect": {"kind": "damage_and_extra_turn_on_kill",
                           "damage_percent": 150, "damage_stat": "elemental"},
            },
            {
                "id": "load_shed",
                "name": "Load Shed",
                "min_rarity": "legendary",
                "resource_cost": 32, "resource_type": "mana", "cooldown": 3,
                "description": "Deal 120% ATK damage — 200% if the target is "
                               "above 60% HP.",
                "effect": {"kind": "damage_bonus_if_target_healthy",
                           "damage_percent": 120, "bonus_damage_percent": 80,
                           "hp_threshold_percent": 60, "damage_stat": "attack"},
            },
        ],
        "ultimate_ability": {
            "id": "total_load_loss",
            "name": "Total Load Loss",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "Spend 18% of its own HP to hit the whole squad, "
                           "harder the more it spent.",
            "effect": {"kind": "sacrifice_hp_aoe_damage", "self_cost_percent": 18,
                       "damage_percent": 95, "damage_stat": "attack",
                       "hp_scaling": 300},
        },
    },
    {
        # A SECOND REGULAR FOR THE VOIDLANDS, which shipped with two and
        # so showed the same boss most runs. Reads differently from both:
        # the Hollow Choir scales with the crowd and Nullstone Bastion is
        # a taunt wall, while this one BANKS and SPENDS.
        #
        # Same correction as Slagjaw Breaker -- see its note. This
        # originally claimed to punish the player's shields, which is not
        # what damage_consumes_shield does. It shields itself and cashes
        # that in, so the fight is about forcing the discharge early
        # rather than about not shielding.
        "name": "The Long Arrears",
        "role": "boss",
        "region_roles": {VOIDLANDS: "regular"},
        "base_stats": {"attack": 33, "defense": 22, "elemental": 18, "speed": 17,
                       "max_hp": 700, "max_mana": 999, "crit_rate": 10,
                       "crit_damage": 170, "recharge": 19},
        "level_scale_percent": 4,
        "active_abilities": [
            {
                "id": "take_it_on_account",
                "name": "Take It On Account",
                "min_rarity": "legendary",
                "resource_cost": 28, "resource_type": "mana", "cooldown": 3,
                "description": "Shield itself for 30% of its max HP.",
                "effect": {"kind": "self_shield_percent_max_hp", "percent": 30},
            },
            {
                "id": "call_the_debt",
                "name": "Call The Debt",
                "min_rarity": "legendary",
                "resource_cost": 30, "resource_type": "mana", "cooldown": 2,
                "description": "Spend all of its own shielding to deal 140% ATK "
                               "damage plus more for every point spent.",
                "effect": {"kind": "damage_consumes_shield", "damage_percent": 140,
                           "percent_per_shield": 0.45, "max_bonus_percent": 260,
                           "damage_stat": "attack"},
            },
        ],
        "ultimate_ability": {
            "id": "settle_in_full",
            "name": "Settle In Full",
            "min_rarity": "legendary",
            "resource_cost": 50, "resource_type": "energy", "cooldown": 3,
            "is_ultimate": True,
            "description": "For 4 turns the whole crew heals for 45% of the "
                           "damage they deal.",
            "effect": {"kind": "team_lifesteal_buff", "percent": 45, "duration": 4},
        },
    },
]

SPECIALIST_SHORT_NAMES: dict[str, str] = {
    "Slagjaw Breaker": "Slagjaw",
    "Overpressure Cell": "Cell",
    "The Opportunist": "Opportunist",
    "Shear Foreman": "Foreman",
    "Ranging Officer": "Ranger",
    "Understudy Medic": "Medic",
    "The Full Measure": "Measure",
    "Sanitation Unit 9": "Unit 9",
    # Not "Choir" -- The Hollow Choir in the Voidlands already has it,
    # and these two share three regions, so a combat log could show two
    # "Choir" lines in one fight. Second short-name collision I have
    # caused; check_ui_labels is the only thing that catches them.
    "Choir Of Small Debts": "Debts",
    "Bulwark Shift": "Bulwark",
    "Deepworks Regulator": "Regulator",
    "Cascade Failure": "Cascade",
    "The Long Arrears": "Arrears",
}
