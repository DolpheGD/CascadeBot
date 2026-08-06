"""
Enemy templates for combat. Deliberately reuse WEAPON_SKILLS / ARTIFACT_SKILLS
/ ULTIMATE_ABILITIES / ARMOR_PASSIVES from bot/game/loot/abilities.py rather
than a separate enemy-ability vocabulary -- an enemy "knowing Flame Strike"
and a weapon that grants Flame Strike are mechanically identical to the
combat engine, so one effect-resolution system covers both. Enemy resource
costs are irrelevant (they have effectively unlimited mana), but the
ultimate is still gated by energy reaching 50 so bosses don't nuke turn one.

Content pass: full roster grounded in the Cascade setting (see
docs/WORLD_LORE.md) -- Xender's regime (Acatrya), Eris-wreckage constructs,
Void-corrupted machinery, and the wastelanders/scavengers Team Cascade
actually runs into on expeditions. No fantasy creatures.

Roles:
  * "combat" -- regular room enemies, plentiful
  * "elite"  -- elite rooms, few per fight
  * "boss"   -- standalone boss-room enemies, 1 per fight.
  * "boss_group_member" -- boss-room enemies that only ever appear
    alongside another boss template, either as part of a BOSS_GROUPS entry
    or as another boss's "escorts" (see get_boss_encounter() /
    _with_escorts()) -- never rolled individually via
    get_templates_by_role("boss").

Combat rework -- solo boss rebalance: bosses were hitting far too hard for
how quickly fights ended, most noticeably in Glacier 15 (the easiest
region) where "XG-23 Heavy Drone" and "Subject 29" also do duty as its
regular/final boss. Every "boss"-role template below had its damage stats
(attack/elemental) cut and max_hp raised so fights read as more drawn-out
wars of attrition instead of bursts -- and XG-23/Subject 29 specifically
were tuned so that, at Glacier 15's own (lowest) scaling, they land only
slightly above "Glacier 15 Custodian" (that region's elite) rather than
far above it. The same templates still scale up further in the harder
regions they also appear in via level_offset, so they stay meaningful
bosses there.
"
Roster-wide balance pass: defense, elite/normal power level, and the
anti-stalemate attack ramp-up (which replaced innate per-turn HP regen)
are now handled uniformly for every template in bot/game/combat/factory.py
(build_enemy_combatant) rather than hand-tuned per entry here -- see that
file's DEFENSE_MULTIPLIER_BY_ROLE / ELITE_POWER_MULTIPLIER /
NORMAL_POWER_MULTIPLIER / ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE comments.
What IS hand-tuned here, as part of the same pass:
  * "actions_per_cycle": 2 is no longer XG-23-exclusive -- a growing
    handful of other fast (high-Speed) templates across all three roles
    now also act twice a cycle (Voidcrest Skitterer, Dolpo, Wasteland
    Colosseum Champion and Sir Vengeance among elites; XG-23 Heavy Drone,
    Corrupted Bli, X-RR, and Rupture among bosses), each with its per-hit
    damage pulled down ~20% to compensate (see each entry's comment) so
    "acts twice for X" reads as roughly comparable pressure to "acts once
    for ~1.6X", not strictly better.
  * AoE actives/ultimates (damage_all_opponents /
    damage_all_opponents_and_debuff -- see bot/game/loot/abilities.py's
    "AoE kit" entries) are now assigned to several templates: slow, tanky
    ones get the hard-hitting versions (Cleave Smash, Meteor Shower, World
    Ender), fast/multi-action ones get the lighter versions (Flurry Slash,
    Arc Lightning, Storm of Blades) -- matching the same
    "slow = hard-hitting, fast = lighter" tradeoff used for
    actions_per_cycle above.

Multi-enemy bosses -- "escorts" pass: some standalone "boss"-role
templates now always bring fixed companions into the fight, distinct from
the rare, randomly-rolled BOSS_GROUPS (Eruptor Trio) below. A boss
template with an "escorts" list (e.g. XG-23 Heavy Drone -> ["XG-23A",
"XG-23B"]) is still rolled through the normal solo-boss odds/region_roles
exactly as before, but get_boss_encounter() automatically appends its
escorts by name every time it's chosen -- so the fight is guaranteed
multi-enemy whenever that boss shows up, not just 1-in-5 like a
BOSS_GROUPS pull. Escort templates use role="boss_group_member" (same as
Eruptor Trio members) so they're never independently rolled as a solo
boss/elite/combat enemy -- they only ever appear via another template's
"escorts" field. Converted this pass: XG-23 Heavy Drone (+XG-23A/XG-23B),
Aerion Mk1 (+Dolpo/Xero), Thedoggyp (+THE BILLIAN), and The Wastelands'
final boss, replaced outright by the Ocellios Transport Crew (NF
+Ocellios Train/Broskm/Duko). Each escorted boss's own base_stats were
pulled down somewhat from their old solo-fight numbers to compensate for
the extra bodies now fighting alongside them, same spirit as the
actions_per_cycle compensation above.
"""

from __future__ import annotations

import random

from bot.game.loot.abilities import (
    ARMOR_PASSIVES,
    ARTIFACT_SKILLS,
    ULTIMATE_ABILITIES,
    WEAPON_SKILLS,
    get_ability_by_id,
)

ENEMY_TEMPLATES: list[dict] = [
    # ---------------------------------------------------------------
    # COMBAT -- regular encounters
    # ---------------------------------------------------------------
    {
        # Beginner-tier: an unaffiliated drifter from outside Acatrya's
        # cities, armed with whatever scrap they could scavenge. The
        # first thing most new operatives fight.
        "name": "Wandering Vagrant",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 10, "defense": 3, "elemental": 1, "speed": 7,
            "max_hp": 32, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "quickdraw_slash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "scrap_armor")],
    },
    {
        # Josh Imitator
        "name": "Josh Imitator",
        "role": "combat",
        "regions": ['Glacier 15', 'The Hotlands', 'Voidcrest Desert'],
        "actions_per_cycle": 2,
        "base_stats": {
            "attack": 3, "defense": 4, "elemental": 3, "speed": 10,
            "max_hp": 12, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 36,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "fracture_field"),
                             get_ability_by_id(WEAPON_SKILLS, "opportunist_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        # Rank-and-file Xender muscle -- crowd control batons, standard
        # issue armor. Seen wherever Acatrya projects authority.
        "name": "Xender Henchmen",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 12, "defense": 5, "elemental": 3, "speed": 8,
            "max_hp": 42, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
    },
    {
        # A step up from Henchmen -- carries incendiary rounds and
        # actually expects to see combat, not just crowd control.
        "name": "Xender Enforcer",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 15, "defense": 7, "elemental": 5, "speed": 9,
            "max_hp": 52, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(WEAPON_SKILLS, "opportunist_strike"),
        ],
        "passive_abilities": [],
    },
    {
        # Dangerous but weak
        "name": "Rohan's Bomb",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 100, "defense": 1, "elemental": 2, "speed": 1,
            "max_hp": 10, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 70,
        },
        "level_scale_percent": 4,
        "active_abilities": [],
        "passive_abilities": [],
    },
    {
        # Dangerous but weak
        "name": "Thedoggyp's gem",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 1, "defense": 1, "elemental": 1, "speed": 100,
            "max_hp": 50, "max_mana": 999, "crit_rate": 1, "crit_damage": 500, "recharge": 70,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 5,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flurry_slash")],
        "passive_abilities": [],
    },
    {
        # Glacier 15's "rogue security drones that never got the
        # shutdown order" -- still patrolling the ruin decades later.
        "name": "Rogue Security Drone",
        "role": "combat",
        "regions": ['Glacier 15'],
        "base_stats": {
            "attack": 10, "defense": 9, "elemental": 5, "speed": 6,
            "max_hp": 58, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst"),
            get_ability_by_id(ARTIFACT_SKILLS, "overclock_repair"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # A squat burrowing rig that works the Voidcrest/Wastelands
        # scrub, surfacing to ram anything that gets close.
        "name": "Dune Digger",
        "role": "combat",
        "regions": ['The Wastelands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 15, "defense": 10, "elemental": 3, "speed": 5,
            "max_hp": 60, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating"),
            get_ability_by_id(ARMOR_PASSIVES, "focused_lens"),
        ],
    },
    {
        # Glacier 15's cold-region counterpart to the Dune Digger -- a
        # drilling unit that never stopped clearing ice tunnels.
        "name": "Glacial Piercer",
        "role": "combat",
        "regions": ['Glacier 15'],
        "base_stats": {
            "attack": 7, "defense": 6, "elemental": 14, "speed": 8,
            "max_hp": 48, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "frost_lance")],
        "passive_abilities": [],
    },
    {
        # A stray, unstable munition off the Void Crevasse -- small,
        # fast, and prone to unpredictable elemental discharge.
        # Balance pass: the roster's fastest normal enemy, so it's also
        # the normal-tier "acts twice a cycle" pick -- attack/elemental
        # pulled down from their old single-action values to compensate,
        # and it carries the light AoE artifact skill (Arc Lightning)
        # instead of a second single-target hit, fitting the "fast =
        # frequent, lighter, sometimes AoE" side of the tradeoff.
        "name": "Voidcrest Skitterer",
        "role": "combat",
        "regions": ['Voidcrest Desert'],
        "base_stats": {
            "attack": 12, "defense": 3, "elemental": 9, "speed": 12,
            "max_hp": 30, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 20,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [],
    },
    {
        # One of the Wastelands' "strikers and protestors" the advanced
        # world left behind -- fighting with improvised gear and real
        # anger, not a paycheck.
        "name": "Wasteland Rebel",
        "role": "combat",
        "regions": ['The Wastelands'],
        "base_stats": {
            "attack": 13, "defense": 5, "elemental": 2, "speed": 9,
            "max_hp": 45, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 25,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sunder_strike"),
            get_ability_by_id(WEAPON_SKILLS, "berserker_rage"),
        ],
        "passive_abilities": [],
    },
    {
        # A fixed Hotlands defense emplacement guarding the Xendium labs
        # -- can't move, doesn't need to.
        "name": "Molten Turret",
        "role": "combat",
        "regions": ['The Hotlands'],
        "base_stats": {
            "attack": 14, "defense": 12, "elemental": 12, "speed": 3,
            "max_hp": 65, "max_mana": 999, "crit_rate": 3, "crit_damage": 150, "recharge": 20,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # Abyssnia crowd control -- networked units that share
        # battlefield data, so putting one down feeds the others.
        "name": "Acatrya Riot Trooper",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Abyssnia'],
        "base_stats": {
            "attack": 13, "defense": 8, "elemental": 3, "speed": 7,
            "max_hp": 50, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "soul_harvest")],
    },
    {
        # A quadrupedal scrapper unit built to hunt down anything that
        # wanders too deep into contested salvage territory.
        # Balance pass: fast (Speed 11) -- carries Flurry Slash, the light
        # AoE weapon skill, for combat-tier AoE variety on a quick target.
        "name": "Scrap Buggy",
        "role": "combat",
        "regions": ['The Wastelands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 15, "defense": 4, "elemental": 2, "speed": 11,
            "max_hp": 38, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 25,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
            get_ability_by_id(WEAPON_SKILLS, "flurry_slash"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "vampiric_edge")],
    },
    {
        # A wastelander half-fused with malfunctioning salvage after too
        # long near a Void-poisoned site -- burns and freezes in the
        # same breath, and doesn't seem to notice either.
        "name": "Corrupted Wastelander",
        "role": "combat",
        "regions": ['The Wastelands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 12, "defense": 5, "elemental": 8, "speed": 7,
            "max_hp": 44, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "power_strike"),
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_scanner"),
        ],
        "passive_abilities": [],
    },
    {
        # Rides with an Acatrya patrol rather than in front of it -- keeps
        # the Henchmen and Enforcers standing (and stocked) so they can
        # keep swinging. A priority target once the party notices what
        # it's doing.
        "name": "Acatrya Field Medic",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Abyssnia'],
        "base_stats": {
            "attack": 4, "defense": 6, "elemental": 5, "speed": 8,
            "max_hp": 65, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 26,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "combat_medic"),
            get_ability_by_id(ARTIFACT_SKILLS, "regenerative_field"),
            get_ability_by_id(ARTIFACT_SKILLS, "ionic_ward"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
    },
    {
        # A coordination drone that doesn't fight so much as make
        # everything around it fight better -- broadcasts targeting data
        # to its own side and jamming static at the party's.
        "name": "Xender Command Relay",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 7, "defense": 7, "elemental": 6, "speed": 7,
            "max_hp": 60, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 35,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
                              get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
    },
    {
        # Roster rounding-out pass: an old ore-hauling automaton from the
        # ruin's original permafrost mining operation, long since repurposed
        # by whatever's left of its programming into "defend the vein."
        # Glacier 15 had the thinnest combat roster of any region -- this
        # and the two entries below give it real variety instead of the
        # same 3 faces on every run.
        "name": "Permafrost Automaton",
        "role": "combat",
        "regions": ['Glacier 15'],
        "base_stats": {
            "attack": 14, "defense": 15, "elemental": 4, "speed": 4,
            "max_hp": 55, "max_mana": 999, "crit_rate": 3, "crit_damage": 145, "recharge": 14,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # Xender's earliest probes into Glacier 15 -- scouting the ruin for
        # recoverable Xendium tech well before the regime commits to a full
        # occupation. Ties the ruin into Acatrya's wider expansion instead
        # of leaving Glacier 15 mechanically isolated from every other
        # region's dominant faction.
        "name": "Xender Recon Scout",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 12, "defense": 4, "elemental": 6, "speed": 10,
            "max_hp": 40, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "tempest_edge")],
        "passive_abilities": [],
    },
    {
        # The Hotlands' only combat-tier enemy used to be the Ash Turret --
        # now replaced by Xendium technology. This particular model is
        # hostile to anything that gets close.
        "name": "Xendium Lab Soldier",
        "role": "combat",
        "regions": ['The Hotlands'],
        "base_stats": {
            "attack": 15, "defense": 4, "elemental": 15, "speed": 6,
            "max_hp": 76, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "scrap_armor")],
    },
    {
        # Voidcrest's second combat-tier enemy
        "name": "Entropy Executor",
        "role": "combat",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 8, "defense": 12, "elemental": 24, "speed": 13,
            "max_hp": 78, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
    },
    {
        # H-Nation only had a presence at elite tier (Vanguard) -- this
        # gives the border dispute a regular-soldier face too, backing up
        # Vanguard operations in the same two regions.
        "name": "H-Nation Border Trooper",
        "role": "combat",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 17, "defense": 8, "elemental": 4, "speed": 9,
            "max_hp": 60, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "rending_cleave")],
        "passive_abilities": [],
    },
    {
        # An earlier, less "successful" Ocellios experiment than the Test
        # Subject elite -- unstable in a smaller way, but still escaped
        # containment. Gives Ocellios a combat-tier face instead of only
        # showing up as an elite.
        "name": "Ocellios Failed Prototype",
        "role": "combat",
        "regions": ['Glacier 15', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 7, "defense": 4, "elemental": 16, "speed": 8,
            "max_hp": 42, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "void_grasp")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "undying_will")],
    },
    {
        # idk
        "name": "Entropy Aura Generator",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 1, "defense": 9, "elemental": 1, "speed": 100,
            "max_hp": 70, "max_mana": 999, "crit_rate": 50, "crit_damage": 101, "recharge": 70,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "jamming_array"),
                             get_ability_by_id(ARTIFACT_SKILLS, "null_field_projector")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell")],
    },
    {
        # idk
        "name": "Voidcell Amplifier",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 1, "defense": 9, "elemental": 1, "speed": 100,
            "max_hp": 75, "max_mana": 999, "crit_rate": 50, "crit_damage": 101, "recharge": 70,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "focused_support_beam"),
                             get_ability_by_id(ARTIFACT_SKILLS, "emergency_relay")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
    },
    {
        # idk
        "name": "Sacrificial Construct",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 1, "defense": 1, "elemental": 1, "speed": 100,
            "max_hp": 90, "max_mana": 999, "crit_rate": 50, "crit_damage": 101, "recharge": 70,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "vitality_offering"),
                             get_ability_by_id(ARTIFACT_SKILLS, "sacrificial_aegis"),
                             get_ability_by_id(ARTIFACT_SKILLS, "purge_beacon"),],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "bloodwell_charm")],
    },
    # ---------------------------------------------------------------
    # ELITE -- tougher
    # ---------------------------------------------------------------
    {
        # Xender's answer to Team Cascade's better-equipped operatives --
        # slower, but built to shrug off small-arms fire.
        # Balance pass: low Speed, high DEF/HP -- exactly the "slow,
        # hard-hitting" profile the AoE kit's heavy option is meant for,
        # so it carries Cleave Smash alongside its single-target kit.
        "name": "Xender Tank",
        "role": "elite",
        "regions": ['The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 23, "defense": 28, "elemental": 6, "speed": 7,
            "max_hp": 170, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 22,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "thornmail"),
            get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        # An Eris-wreckage construct reactivated by leaking Void-matter --
        # not built by anyone still alive to ask about it.
        "name": "Voidwarp Construct",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 12, "defense": 14, "elemental": 22, "speed": 9,
            "max_hp": 140, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 16,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "last_stand"),
    },
    {
        # A grifter who's built a whole act around impersonating Rex
        "name": "Illusion of Rex",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 8, "defense": 8, "elemental": 9, "speed": 20,
            "max_hp": 100, "max_mana": 999, "crit_rate": 15, "crit_damage": 170, "recharge": 27,
        },
        "level_scale_percent": 5,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(WEAPON_SKILLS, "berserker_rage"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "phoenix_rebirth"),
    },
    {
        # An H-Nation soldier operating past the border they're
        # technically not supposed to cross since Xender froze them out
        # of Void-matter synthesis -- a live reminder the old peace is
        # fraying.
        "name": "H-Nation Vanguard",
        "role": "elite",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 25, "defense": 12, "elemental": 5, "speed": 10,
            "max_hp": 180, "max_mana": 999, "crit_rate": 14, "crit_damage": 180, "recharge": 19,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
    },
    {
        # One of Ocellios Labs' "unauthorized experiments" that got out
        # -- unstable, in visible pain, and dangerous in ways that don't
        # look like a normal soldier's.
        "name": "Ocellios Test Subject",
        "role": "elite",
        "regions": ['Glacier 15', 'The Hotlands'],
        "base_stats": {
            "attack": 13, "defense": 9, "elemental": 23, "speed": 11,
            "max_hp": 135, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 20,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "soul_siphon"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "second_wind"),
                              get_ability_by_id(ARMOR_PASSIVES, "undying_will")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "meteor_ultimate"),
    },
    {
        # A Xendium supercomputer lab security unit stuck in an
        # overcharge loop -- it never runs dry, it just keeps firing.
        "name": "Xendium Overcharge Drone",
        "role": "elite",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 16, "defense": 10, "elemental": 20, "speed": 9,
            "max_hp": 145, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 19,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(ARTIFACT_SKILLS, "empowering_ritual"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    {
        # A heavier-duty cousin of the Rogue Security Drone -- Glacier
        # 15's ruin has more than one tier of unit that never got the
        # shutdown order.
        "name": "Glacial Exterminator",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 7, "defense": 16, "elemental": 16, "speed": 8,
            "max_hp": 180, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 17,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_scanner"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    {
        # Roster rounding-out pass: Glacier 15 previously had only one
        # elite template (Custodian), so every elite room in that region
        # was the same fight. This is the ruin's deepest vault guardian --
        # bigger and far better armored than the Custodians patrolling the
        # surface levels, exclusive to Glacier 15 so the region's elite
        # rooms actually vary.
        "name": "Permafrost Guardian",
        "role": "elite",
        "regions": ['Glacier 15'],
        "base_stats": {
            "attack": 13, "defense": 24, "elemental": 12, "speed": 6,
            "max_hp": 205, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 26,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
            get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        # Every other elite represents an official faction or a construct
        # -- The Wastelands (the hub region) had zero elite exclusive to
        # it, despite hosting the anti-Acatrya resistance at combat tier
        # (Wasteland Striker). This is that resistance's champion: better
        # scavenged gear, real charisma, and the same fighting style
        # scaled up.
        # Balance pass: was the single hardest-hitting elite in the whole
        # roster (ATK 30, well clear of the next-highest at 25) despite
        # already having the second-highest Speed among elites -- an easy
        # "acts twice a cycle" pick. ATK/ELE pulled down ~20% (matching the
        # roster's existing multi-action compensation) so 2 actions/cycle
        # reads as roughly comparable pressure to 1 action at the old
        # numbers, not strictly better.
        "name": "Wasteland Colosseum Champion",
        "role": "elite",
        "regions": ['The Wastelands'],
        "base_stats": {
            "attack": 24, "defense": 10, "elemental": 5, "speed": 12,
            "max_hp": 220, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 17,
        },
        "level_scale_percent": 5,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sunder_strike"),
            get_ability_by_id(WEAPON_SKILLS, "berserker_rage"),
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "phoenix_rebirth"),
    },
    {
        # Sir vengeance
        "name": "Sir Vengeance",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 17, "defense": 3, "elemental": 6, "speed": 23,
            "max_hp": 230, "max_mana": 999, "crit_rate": 10, "crit_damage": 280, "recharge": 25,
        },
        "level_scale_percent": 5,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "null_field_projector"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "gale_ascendant"),
    },
    {
        #The Giveaway
        "name": "The Giveaway",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 4, "defense": 1, "elemental": 4, "speed": 23,
            "max_hp": 300, "max_mana": 999, "crit_rate": 10, "crit_damage": 280, "recharge": 40,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "fracture_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    {
        # Voidcrest-exclusive: a still-active guardian drone dug out of
        # deep Eris wreckage in the Void Crevasse, running on tech no
        # living faction can replicate. First enemy in the roster to
        # carry the Mythic-tier weapon/artifact kit added alongside the
        # Eris/Genesis gear sets (see bot/game/loot/abilities.py) -- a
        # preview of that power level before Eris Sentinel below.
        "name": "Corrupted Eris Sentry",
        "role": "elite",
        "regions": ['Voidcrest Desert'],
        "base_stats": {
            "attack": 20, "defense": 10, "elemental": 22, "speed": 14,
            "max_hp": 240, "max_mana": 999, "crit_rate": 12, "crit_damage": 190, "recharge": 22,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "ruin_breaker"),
            get_ability_by_id(WEAPON_SKILLS, "voidpiercer"),
            get_ability_by_id(ARTIFACT_SKILLS, "overmind_surge"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    # ---------------------------------------------------------------
    # Regular Bosses -- standalone 
    # ---------------------------------------------------------------
    {
        # Acatrya's heavy air-superiority unit -- fast, well-armed, and
        # deployed wherever Xender wants a show of force from above.
        # Cycle turn order rework: this is the "actions_per_cycle" example
        # -- as the fastest boss in the roster it now also acts TWICE every
        # cycle (see bot/game/combat/battle.py), on top of already going
        # earlier each cycle from its high Speed. Remove/adjust this field
        # (or add it to any other combat/elite/boss template) to tune how
        # often a given enemy acts per cycle; it defaults to 1 if omitted.
        # Balance pass: no longer the roster's only multi-action enemy (see
        # module docstring) -- it keeps the archetype but now also carries
        # Storm of Blades, the lighter AoE ultimate, matching "fast =
        # frequent + lighter, sometimes AoE" rather than a single big hit.
        # Escorts pass: now permanently flies escort with two weak support
        # drones (XG-23A/XG-23B, below) -- its own ATK/ELE/HP were pulled
        # down from the old solo-fight numbers (28/12/310) to compensate
        # for the extra bodies and extra buffs/shields those drones bring.
        "name": "XG-23 Heavy Drone",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Wastelands': 'regular', 'The Hotlands': 'regular'},
        "base_stats": {
            "attack": 26, "defense": 10, "elemental": 12, "speed": 14,
            "max_hp": 320, "max_mana": 999, "crit_rate": 14, "crit_damage": 170, "recharge": 20,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "escorts": ["XG-23A", "XG-23B"],
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum"),
                              get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "storm_of_blades"),
    },
    {
        # XG-23's escort -- a stripped-down support drone, cheap enough
        # that Xender fields two of them per Heavy Drone. Barely fights;
        # its job is keeping the Heavy Drone's ATK topped up.
        "name": "XG-23A",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 11, "defense": 12, "elemental": 4, "speed": 9,
            "max_hp": 105, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
    },
    {
        # XG-23's other escort -- same stripped-down chassis as XG-23A,
        # fielded with a defensive kit instead so the pair covers both
        # offense and survivability support.
        "name": "XG-23B",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 18, "defense": 5, "elemental": 4, "speed": 8,
            "max_hp": 85, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "aegis_broadcast")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator")],
    },
    {
        # regular boss for all areas
        # Balance pass: slow (Speed 8) and by far the tankiest regular
        # boss (520 base HP) -- the "slow, hard-hitting" AoE profile, so
        # it picks up Cleave Smash alongside its support kit.
        # NOT IN GLACIER 15. At 520 HP it was nearly double the other
        # regular bosses in the first region's pool (270-300), so which
        # boss a new player drew decided their run before it started.
        # It keeps every later region, and the story now uses it as the
        # prologue's un-killable hazard -- so "it comes back as a boss
        # later" is literally true.
        "name": "Boss John's Driller Prototype",
        "role": "boss",
        "region_roles": {'The Wastelands': 'regular', 'The Hotlands': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 37, "defense": 12, "elemental": 32, "speed": 4,
            "max_hp": 520, "max_mana": 999, "crit_rate": 19, "crit_damage": 170, "recharge": 30,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "fracture_field"),
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),   
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "undying_will")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    {
        # Roster rounding-out pass: Glacier 15 and The Wastelands each had
        # exactly ONE "regular" (non-final) boss template -- XG-23 Heavy
        # Drone -- so every checkpoint boss in a run through either region
        # was the same fight repeated. SAJ II
        "name": "SAJ II",
        "role": "boss",
        "region_roles": {'The Wastelands': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 24, "defense": 8, "elemental": 40, "speed": 14,
            "max_hp": 460, "max_mana": 999, "crit_rate": 10, "crit_damage": 150, "recharge": 26,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        # HHyper ship, the first of its kind deployed to the region
        # Escorts pass: now always flies with two of its crew fighting
        # alongside it -- Dolpo (fast, hybrid support/striker) and Xero
        # (steadier, ally-buffing) -- both "medium" in weight class, well
        # above XG-23's throwaway drones. Own ATK/ELE/HP pulled down from
        # the old solo-fight numbers (34/25/430) to compensate.
        "name": "Aerion Mk1",
        "role": "boss",
        "region_roles": {'The Hotlands': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 30, "defense": 10, "elemental": 33, "speed": 10,
            "max_hp": 440, "max_mana": 999, "crit_rate": 13, "crit_damage": 175, "recharge": 13,
        },
        "level_scale_percent": 4,
        "escorts": ["Dolpo", "Xero"],
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
    },
    {
        # Aerion Mk1's fastest crewman -- the real Dolpo the Voidcrest
        # grifter "Dolpo Impersonator" (see elite roster) built his whole
        # act copying. Splits time between energy/mana support for the
        # ship and quick speed-scaled strikes of his own.
        "name": "Dolpo",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 18, "defense": 9, "elemental": 10, "speed": 15,
            "max_hp": 190, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "tempest_edge"),
            get_ability_by_id(ARTIFACT_SKILLS, "power_transfer"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
    },
    {
        # Aerion Mk1's other crewman -- steadier than Dolpo, keeps the
        # ship's weakest-off ally topped up on offense while it holds
        # the line itself.
        "name": "Xero",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 22, "defense": 11, "elemental": 12, "speed": 11,
            "max_hp": 220, "max_mana": 999, "crit_rate": 8, "crit_damage": 150, "recharge": 19,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "focused_support_beam"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # HHyper's Elite Unit -- a corrupted version of the standard Bli design
        # Balance pass: the fastest non-XG-23 boss (Speed 16) -- the
        # roster's other multi-action pick, with attack/elemental pulled
        # down to compensate for the extra action per cycle.
        # NOT IN GLACIER 15 -- same reason as the Driller: 420 HP and
        # three actions a cycle is not a tier-1 regular boss. Keeps
        # Voidcrest, where it was buffed to belong.
        "name": "Corrupted Bli",
        "role": "boss",
        "region_roles": {'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 19, "defense": 9, "elemental": 22, "speed": 22,
            "max_hp": 420, "max_mana": 999, "crit_rate": 8, "crit_damage": 180, "recharge": 18,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flurry_slash"),
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum"),
                              get_ability_by_id(ARMOR_PASSIVES, "second_wind")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Thedoggyp and Billian
        "name": "Thedoggyp",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Wastelands': 'regular', 'The Hotlands': 'regular'},
        "base_stats": {
            "attack": 29, "defense": 11, "elemental": 12, "speed": 10,
            "max_hp": 300, "max_mana": 999, "crit_rate": 4, "crit_damage": 200, "recharge": 22,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 4,
        "escorts": ["THE BILLIAN"],
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flurry_slash"),
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "soul_harvest")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    {
        # Thedoggyp's escort -- huge, slow, and built to do one thing:
        # stand there absorbing hits and keeping Thedoggyp topped up and
        # shielded. Carries zero offensive abilities by design.
        "name": "THE BILLIAN",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 11, "defense": 20, "elemental": 9, "speed": 3,
            "max_hp": 260, "max_mana": 999, "crit_rate": 2, "crit_damage": 500, "recharge": 20,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "jamming_array"),
            get_ability_by_id(ARTIFACT_SKILLS, "vitality_offering"),
            get_ability_by_id(ARTIFACT_SKILLS, "aegis_broadcast"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        # Triv the troll
        "name": "Triv",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Hotlands': 'regular'},
        "base_stats": {
            "attack": 17, "defense": 6, "elemental": 11, "speed": 10,
            "max_hp": 320, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 18,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "escorts": ["Loona"],
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "opportunist_strike"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "fracture_field"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_scanner"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        # Triv's girlfriend
        # Loona is NOT in The Hotlands. At 170 HP she sat in a regular
        # boss pool that also held the 520 HP Driller -- a 3.1x spread,
        # which means the draw decided the run rather than the player.
        # Same failure the first region had. tools/check_progression.py
        # asserts the spread now.
        "name": "Loona",
        "role": "boss_group_member",
        "region_roles": {'Glacier 15': 'regular'},
        "base_stats": {
            "attack": 27, "defense": 8, "elemental": 21, "speed": 15,
            "max_hp": 210, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 18,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "opportunist_strike"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "purge_beacon"),
            get_ability_by_id(ARTIFACT_SKILLS, "emergency_relay"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "second_wind")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    # ---------------------------------------------------------------
    # FINAL BOSSES
    # ---------------------------------------------------------------
    {
        # Mechanical worm in Glacier 15
        # Balance pass: Glacier 15's final boss gets the roster's signature
        # hard-hitting AoE ultimate -- a worm burrowing through and hitting
        # the whole party at once reads better than a single meteor, and
        # it gives the region's capstone fight a real "everyone's in
        # danger" moment.
        # 380 HP, DOWN FROM 700.
        #
        # This is the capstone of the FIRST region, and the ladder of
        # final bosses ran 700 -> 420 -> 950 -> 1050 -> 1500: Glacier's
        # gate was two thirds bigger than the one after it. Since a
        # region only unlocks by clearing the one before, an inverted
        # first rung locks the entire game behind it -- measured at 3%
        # clear for a level-1 squad, which is precisely who the prologue
        # now delivers here.
        #
        # 380 keeps it the hardest thing in Glacier 15 by a distance
        # (regular bosses there top out at 300) while putting the ladder
        # in order: 380 -> 560 -> 950 -> 1050 -> 1500.
        "name": "Void Hydra",
        "role": "boss",
        "region_roles": {'Glacier 15': 'final'},
        "base_stats": {
            "attack": 34, "defense": 8, "elemental": 22, "speed": 11,
            "max_hp": 510, "max_mana": 999, "crit_rate": 16, "crit_damage": 185, "recharge": 25,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
            get_ability_by_id(ARTIFACT_SKILLS, "fracture_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    {
        # The Wastelands' final boss -- replacing the old solo Negadom.
        # The Ocellios Transport Crew is a hijacked Ocellios Labs supply
        # train and its three riders, escaped Wastelands way and now
        # running its own racket. NF is the crew's face and its most
        # well-rounded fighter -- carries the group's signature AoE
        # ultimate -- while the Train (pure tank/buff), Broskm (healer),
        # and Duko (glass-cannon striker) round the fight out. Total
        # party power is comparable to the old solo Negadom's, just
        # spread across four bodies instead of concentrated in one.
        "name": "NF",
        "role": "boss",
        "region_roles": {'The Wastelands': 'final'},
        "base_stats": {
            "attack": 26, "defense": 16, "elemental": 26, "speed": 11,
            "max_hp": 420, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 13,
        },
        "level_scale_percent": 4,
        "escorts": ["Ocellios Train", "Broskm", "Duko"],
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(WEAPON_SKILLS, "sunder_strike"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
            get_ability_by_id(ARMOR_PASSIVES, "momentum"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    {
        # The crew's ride and heaviest member -- absurdly tanky, and
        # doesn't do much besides keep the other three buffed and
        # shielded. By far the highest DEF/HP in the fight, but nearly
        # harmless if it's somehow the last one standing.
        "name": "Ocellios Train",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 10, "defense": 40, "elemental": 8, "speed": 4,
            "max_hp": 530, "max_mana": 999, "crit_rate": 3, "crit_damage": 120, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "focused_support_beam"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        # One of the train's riders -- support and healing-oriented,
        # keeps the crew's HP up passively every turn on top of its
        # active heals.
        "name": "Broskm",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 8, "defense": 14, "elemental": 16, "speed": 9,
            "max_hp": 260, "max_mana": 999, "crit_rate": 6, "crit_damage": 140, "recharge": 10,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "combat_medic"),
            get_ability_by_id(ARTIFACT_SKILLS, "purge_beacon"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "phoenix_rebirth"),
    },
    {
        # The train's other rider -- a glass cannon. Hits far harder
        # than anyone else in the crew, including NF, but has the
        # lowest DEF/HP of the four by a wide margin.
        "name": "Duko",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 12, "defense": 5, "elemental": 42, "speed": 14,
            "max_hp": 180, "max_mana": 999, "crit_rate": 20, "crit_damage": 200, "recharge": 9,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # A Hotlands war-machine slagged and refused down to its core by
        # a Xendium reactor overload -- still walking, still armed.
        # Balance pass: had by far the highest ATK of any boss in the
        # roster (45, next-highest final boss was 33) on top of solid
        # Speed (13) -- an obvious "acts twice a cycle" pick to make its
        # capstone fight feel appropriately climactic. ATK/ELE pulled down
        # ~20% to compensate, same ratio used everywhere else, which also
        # brings its per-hit numbers back in line with its fellow final
        # bosses instead of dwarfing them.
        "name": "X-RR",
        "role": "boss",
        "region_roles": {'The Hotlands': 'final'},
        "base_stats": {
            "attack": 46, "defense": 12, "elemental": 40, "speed": 28,
            "max_hp": 1050, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 24,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(ARTIFACT_SKILLS, "null_field_projector"),
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
            get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Voidcrest Desert previously had NO solo final boss at all --
        # its "final" role was 100% covered by the Eruptor Trio BOSS_GROUPS
        # entry (see get_boss_encounter()'s "Bugfix" comment below), so
        # every single Voidcrest capstone fight was guaranteed to be that
        # same 3-enemy encounter. This gives it a real solo alternative,
        # and doubles as the roster's showcase for the newest Divine-tier
        # kit (see bot/game/loot/abilities.py's Mythic/Divine gap-fill
        # pass) -- Temporal Capacitor alone effectively doubles its action
        # economy (base_actions_per_cycle 1 + the passive's +1 bonus, see
        # Combatant.actions_per_cycle()), so no separate
        # "actions_per_cycle": 2 is set here to avoid stacking two
        # extra-action sources into three actions a cycle.
        "name": "Boss John",
        "role": "boss",
        "region_roles": {'Voidcrest Desert': 'final'},
        "base_stats": {
            "attack": 56, "defense": 14, "elemental": 40, "speed": 28,
            "max_hp": 1350, "max_mana": 999, "crit_rate": 15, "crit_damage": 195, "recharge": 28,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "cataclysms_edge"),
            get_ability_by_id(WEAPON_SKILLS, "apex_predator"),
            get_ability_by_id(ARTIFACT_SKILLS, "absolute_zero"),
            get_ability_by_id(ARTIFACT_SKILLS, "astral_cascade"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "temporal_capacitor")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
    },
    # ---------------------------------------------------------------
    # ABYSSNIA -- the glittering capital of Acatrya (see docs/WORLD_LORE.md).
    # Tier 5, the true endgame: Xender's own seat of power, guarded by
    # riot police, corporate security, and true believers, with an
    # underclass that never made it into the brochure. First region to
    # showcase the newer engine mechanics (see bot/game/combat/effects.py's
    # "New-mechanics pass" docstring) on the ENEMY side rather than just
    # player kits -- Propaganda Broadcast Unit (on_hit_team_buff), Acatrya
    # Prime Enforcer (apply_vulnerability_stack), and Xender himself
    # (extra_turn_on_kill) all carry gear built on them.
    # ---------------------------------------------------------------
    {
        "name": "Skyline Enforcer",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 16, "defense": 10, "elemental": 4, "speed": 11,
            "max_hp": 65, "max_mana": 999, "crit_rate": 8, "crit_damage": 155, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "quickdraw_slash"),
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # A swarm of repurposed advertisement drones -- fast and numerous,
        # never actually built to fight, but there are a lot of them.
        "name": "Ad-Drone Swarm Unit",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 10, "defense": 5, "elemental": 14, "speed": 18,
            "max_hp": 50, "max_mana": 999, "crit_rate": 10, "crit_damage": 160, "recharge": 14,
        },
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flurry_slash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
    },
    {
        # The "fifth of the population" the capital's ads never mention --
        # desperate, opportunistic, and taking it out on whoever Cascade
        # sends in, not entirely without reason.
        "name": "Undercity Scavenger",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 14, "defense": 6, "elemental": 3, "speed": 10,
            "max_hp": 58, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "opportunist_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "vampiric_edge")],
    },
    {
        "name": "Corporate Security Mech",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 19, "defense": 14, "elemental": 5, "speed": 7,
            "max_hp": 85, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "power_strike"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
    },
    {
        # A true believer in Xender's regime, rallied by broadcasts the
        # rest of the capital tunes out.
        "name": "Xender Loyalist",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 15, "defense": 8, "elemental": 8, "speed": 12,
            "max_hp": 60, "max_mana": 999, "crit_rate": 9, "crit_damage": 160, "recharge": 15,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
    },
    {
        "name": "Tower Maintenance Bot",
        "role": "combat",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 12, "defense": 9, "elemental": 6, "speed": 6,
            "max_hp": 70, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 20,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "overclock_repair")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "scrap_armor")],
    },
    {
        "name": "Acatrya Elite Guard",
        "role": "elite",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 26, "defense": 16, "elemental": 6, "speed": 13,
            "max_hp": 260, "max_mana": 999, "crit_rate": 13, "crit_damage": 175, "recharge": 22,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "storm_of_blades"),
    },
    {
        # First enemy to carry on_hit_team_buff (see bot/game/loot/
        # abilities.py's Rallying Plate) -- the whole point of a
        # "broadcast" unit is that hitting it just makes it louder.
        "name": "Propaganda Broadcast Unit",
        "role": "elite",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 18, "defense": 12, "elemental": 18, "speed": 11,
            "max_hp": 230, "max_mana": 999, "crit_rate": 11, "crit_damage": 170, "recharge": 20,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "rallying_plate")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        "name": "Skybridge Sentinel",
        "role": "elite",
        "regions": ['Abyssnia'],
        "base_stats": {
            "attack": 24, "defense": 13, "elemental": 8, "speed": 20,
            "max_hp": 240, "max_mana": 999, "crit_rate": 15, "crit_damage": 185, "recharge": 20,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "tempest_edge"),
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "gale_ascendant"),
    },
    {
        # ---------------------------------------------------------------
        # Regular Bosses -- Abyssnia
        # ---------------------------------------------------------------
        # Ocellios Labs founder Stubby's contingency plan, in case his own
        # creations ever needed to be put down. Nobody's needed to use it
        # until now.
        "name": "Rohan's Catastrophe Soldier",
        "role": "boss",
        "region_roles": {'Abyssnia': 'regular'},
        "base_stats": {
            "attack": 28, "defense": 15, "elemental": 22, "speed": 12,
            "max_hp": 480, "max_mana": 999, "crit_rate": 13, "crit_damage": 180, "recharge": 22,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
            get_ability_by_id(ARTIFACT_SKILLS, "system_purge"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        # Xender's top enforcer -- carries Weakpoint Marker (see
        # bot/game/loot/abilities.py), marking whoever Xender himself
        # wants softened up before the real fight.
        "name": "Acatrya Prime Enforcer",
        "role": "boss",
        "region_roles": {'Abyssnia': 'regular'},
        "base_stats": {
            "attack": 32, "defense": 17, "elemental": 10, "speed": 14,
            "max_hp": 520, "max_mana": 999, "crit_rate": 15, "crit_damage": 190, "recharge": 20,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_marker"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    {
        # Abyssnia's final boss -- and the story's actual antagonist (see
        # docs/WORLD_LORE.md): the leader of Acatrya himself, in the
        # capital he built on Void-matter rights he never should have
        # gotten exclusively. The hardest single fight in the game --
        # Divine-tier kit across the board, and Momentum Core
        # (extra_turn_on_kill) means every kill he lands just keeps the
        # fight going for him, not the party.
        "name": "Xender",
        "role": "boss",
        "region_roles": {'Abyssnia': 'final'},
        "base_stats": {
            "attack": 67, "defense": 20, "elemental": 44, "speed": 18,
            "max_hp": 1800, "max_mana": 999, "crit_rate": 18, "crit_damage": 210, "recharge": 28,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "apex_predator"),
            get_ability_by_id(ARTIFACT_SKILLS, "absolute_zero"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_marker"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum_core")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    # ---------------------------------------------------------------
    # BOSS GROUP -- the Eruptor Trio. Three enemies fought as a single,
    # very difficult boss encounter (see BOSS_GROUPS / get_boss_encounter
    # below). role="boss_group_member" keeps them out of the normal
    # single-boss roll -- they only ever show up together.
    # ---------------------------------------------------------------
    {
        # The Trio's ground anchor: a massive tunnel-boring rig that
        # surfaced mid-dig and never stopped drilling.
        "name": "Borehole",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 58, "defense": 12, "elemental": 16, "speed": 5,
            "max_hp": 530, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 26,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating"),
                              get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell"),],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    {
        # The Trio's flier: a three-eyed combat mech bristling with
        # every weapon system that would fit on the frame.
        # Balance pass: the Trio's fastest member by a wide margin (Speed
        # 13 vs Borehole's 5 and Gatekeeper's 8) -- fits the "acts twice a
        # cycle" archetype used elsewhere on the roster's fastest units.
        # ATK/ELE pulled down ~20% to compensate, same ratio as everywhere
        # else; Borehole and Gatekeeper are untouched since they're
        # already the "slow, hard-hitting" side of the Trio's tradeoff.
        "name": "Rupture",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 20, "defense": 10, "elemental": 27, "speed": 13,
            "max_hp": 420, "max_mana": 999, "crit_rate": 14, "crit_damage": 175, "recharge": 27,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(WEAPON_SKILLS, "opportunist_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "gale_ascendant"),
    },
    {
        # The Trio's brain: an oversized display rig that never leaves
        # the back of the chamber, directing every blaster and cannon
        # wired into it -- and, worse, actively coordinating with the
        # other two. Keeping this one alive keeps Borehole and Rupture
        # both hitting harder and patching themselves back up, which is
        # most of what makes this fight "very difficult."
        # Balance pass: never leaves the back of the chamber (lowest Speed
        # in the Trio) and hits hardest -- carries Meteor Shower, the
        # heavy AoE artifact skill, on top of its support/debuff kit.
        "name": "Gatekeeper",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 23, "defense": 16, "elemental": 30, "speed": 8,
            "max_hp": 680, "max_mana": 999, "crit_rate": 50, "crit_damage": 120, "recharge": 28,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "aegis_broadcast"),
            get_ability_by_id(ARTIFACT_SKILLS, "emergency_relay"),
            get_ability_by_id(ARTIFACT_SKILLS, "jamming_array"),
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
            get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    # ---------------------------------------------------------------
    # BOSS GROUP -- Acatrya's Board. A second named trio, this one for
    # Abyssnia -- deliberately a REGULAR checkpoint-boss alternative
    # rather than reserved for the final slot the way the Eruptor Trio
    # is for Voidcrest, since Xender himself is Abyssnia's one and only
    # final boss and doesn't need competition for that slot. Each member
    # plays a distinct role in a boardroom rather than a battlefield --
    # the tank protects, the auditor strips defenses down to capitalize
    # on them, the censor silences whoever's causing the most trouble.
    # ---------------------------------------------------------------
    {
        "name": "Exiled Acid",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 30, "defense": 22, "elemental": 10, "speed": 8,
            "max_hp": 700, "max_mana": 999, "crit_rate": 10, "crit_damage": 160, "recharge": 24,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(ARTIFACT_SKILLS, "empowering_ritual"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        # Strips defenses down first, then her own ultimate (null_strike's
        # damage_bonus_if_debuffed) capitalizes on exactly the DEF debuffs
        # she just applied -- a self-contained combo in one kit.
        "name": "Exiled APS",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 22, "defense": 14, "elemental": 20, "speed": 12,
            "max_hp": 480, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 22,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        "name": "Exiled JP",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 18, "defense": 12, "elemental": 24, "speed": 15,
            "max_hp": 450, "max_mana": 999, "crit_rate": 14, "crit_damage": 175, "recharge": 20,
        },
        "level_scale_percent": 5,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(ARTIFACT_SKILLS, "jamming_array"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },

    # ==================================================================
    # ROSTER EXPANSION -- "enemies that use the player's mechanics".
    #
    # Two problems this fixes at once.
    #
    # 1. COVERAGE. The roster was heavily front-loaded: Glacier 15 (the
    #    starting region) had 17 normal enemies while Abyssnia (the
    #    endgame) had 8, so the region a player spends the most time in
    #    repeated itself the most. The additions below are weighted to
    #    the late regions.
    #
    # 2. DEAD MECHANICS. Several effect kinds existed in the engine with
    #    nothing using them -- most importantly damage_and_self_taunt,
    #    which meant the ENEMY half of the taunt system was unreachable.
    #    Taunt was only ever something the player did TO enemies; an
    #    enemy that forces you to chew through it before you can reach
    #    the healer behind it never existed. The bodyguard/warden
    #    templates below are that fight, and they're deliberately paired
    #    with support enemies worth protecting -- a taunter guarding
    #    nothing is just a durable enemy.
    #
    # Stat blocks are set against the per-region medians for their role
    # (combat ~50-62 HP, elite ~180-235, boss ~450) rather than invented,
    # so these slot into existing encounter difficulty rather than
    # spiking it.
    # ==================================================================

    # --- Taunting bodyguards. The counterpart to the player's tank. ---
    {
        "name": "Bulwark Sentinel",
        "role": "combat",
        "regions": ["Glacier 15", "The Wastelands"],
        "base_stats": {"attack": 7, "defense": 11, "elemental": 2, "speed": 6,
                       "max_hp": 78, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 12},
        "level_scale_percent": 4,
        # Introduced early and cheaply on purpose: this is where a player
        # first meets forced targeting, on an enemy slow and weak enough
        # that learning the rule costs them very little.
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        "name": "Ashplate Warden",
        "role": "elite",
        "regions": ["The Hotlands", "Voidcrest Desert"],
        "base_stats": {"attack": 15, "defense": 16, "elemental": 6, "speed": 9,
                       "max_hp": 240, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 15},
        "level_scale_percent": 4,
        "max_poise": 14,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge"),
            get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "aegis_protocol"),
    },
    {
        "name": "Abyssal Custodian",
        "role": "elite",
        "regions": ["Abyssnia"],
        "base_stats": {"attack": 19, "defense": 18, "elemental": 9, "speed": 14,
                       "max_hp": 265, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 16},
        "level_scale_percent": 4,
        "max_poise": 16,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge"),
            get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "provoking_aura")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "last_stand"),
    },

    # --- Support enemies: the reason a bodyguard is worth killing. ---
    {
        "name": "Wastes Fieldmedic",
        "role": "combat",
        "regions": ["The Wastelands", "The Hotlands"],
        "base_stats": {"attack": 6, "defense": 5, "elemental": 8, "speed": 10,
                       "max_hp": 46, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 14},
        "level_scale_percent": 4,
        # Low HP and high value -- exactly the target a player wants to
        # burst, which is what makes a taunter standing in front of it a
        # real problem rather than a stat check.
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "healing_light")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator")],
    },
    {
        "name": "Choir of Ledgers",
        "role": "combat",
        "regions": ["Abyssnia"],
        "base_stats": {"attack": 11, "defense": 9, "elemental": 14, "speed": 12,
                       "max_hp": 70, "max_mana": 999, "crit_rate": 7, "crit_damage": 160, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
    },

    # --- Corrosion line: enemy-side DoT amplification. ---
    {
        "name": "Rustlung Crawler",
        "role": "combat",
        "regions": ["The Wastelands", "Voidcrest Desert"],
        "base_stats": {"attack": 9, "defense": 4, "elemental": 11, "speed": 12,
                       "max_hp": 52, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 14},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "corrosive_mark")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "accelerant_coating")],
    },
    {
        "name": "Blightspire Adept",
        "role": "elite",
        "regions": ["Voidcrest Desert", "Abyssnia"],
        "base_stats": {"attack": 14, "defense": 9, "elemental": 21, "speed": 18,
                       "max_hp": 215, "max_mana": 999, "crit_rate": 10, "crit_damage": 170, "recharge": 18},
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "blight_cloud"),
            get_ability_by_id(ARTIFACT_SKILLS, "corrosive_mark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "accelerant_coating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },

    # --- Break-focused enemies: pressure the player's own poise plan. ---
    {
        "name": "Concussion Drone",
        "role": "combat",
        "regions": ["Glacier 15", "The Hotlands"],
        "base_stats": {"attack": 10, "defense": 5, "elemental": 4, "speed": 13,
                       "max_hp": 44, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 15},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "emp_burst")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
    },
    {
        "name": "Shatterjaw Reaver",
        "role": "elite",
        "regions": ["The Hotlands", "Voidcrest Desert"],
        "base_stats": {"attack": 20, "defense": 8, "elemental": 6, "speed": 16,
                       "max_hp": 200, "max_mana": 999, "crit_rate": 13, "crit_damage": 175, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "jamming_array")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "storm_of_blades"),
    },

    # --- Late-region filler, plain but distinct, to thin out repeats. ---
    {
        "name": "Duneglass Stalker",
        "role": "combat",
        "regions": ["Voidcrest Desert"],
        "base_stats": {"attack": 12, "defense": 4, "elemental": 6, "speed": 17,
                       "max_hp": 48, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 14},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flurry_slash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
    },
    {
        "name": "Hollow Auditor",
        "role": "combat",
        "regions": ["Abyssnia"],
        "base_stats": {"attack": 15, "defense": 9, "elemental": 8, "speed": 11,
                       "max_hp": 68, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 15},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "power_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating")],
    },
    {
        "name": "Nullwrit Enforcer",
        "role": "combat",
        "regions": ["Abyssnia"],
        "base_stats": {"attack": 16, "defense": 11, "elemental": 6, "speed": 8,
                       "max_hp": 82, "max_mana": 999, "crit_rate": 7, "crit_damage": 160, "recharge": 13},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        "name": "Cinderveil Acolyte",
        "role": "combat",
        "regions": ["The Hotlands", "Abyssnia"],
        "base_stats": {"attack": 10, "defense": 6, "elemental": 15, "speed": 12,
                       "max_hp": 58, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 16},
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "focused_lens")],
    },

    # --- A boss built entirely around the new mechanics. ---
    {
        # Fights as a protected backline: the Lector itself is a fragile,
        # high-output caster that permanently taunts through its own
        # escorts. The intended solution is the mechanic the player has
        # by now -- break the wardens to drop the taunt, or bring AOE,
        # which taunt explicitly does not redirect.
        "name": "Rohan's Negadom",
        "role": "boss",
        "region_roles": {"Voidcrest Desert": "regular", "Abyssnia": "regular"},
        "base_stats": {"attack": 26, "defense": 12, "elemental": 30, "speed": 15,
                       "max_hp": 830, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 20},
        "level_scale_percent": 4,
        "actions_per_cycle": 2,
        "max_poise": 18,
        "escorts": ["Negadom Destroyer", "Negadom Destroyer"],
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "blight_cloud"),
            get_ability_by_id(ARTIFACT_SKILLS, "corrosive_mark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        "name": "Negadom Destroyer",
        "role": "boss_group_member",
        "regions": [],
        "base_stats": {"attack": 13, "defense": 17, "elemental": 5, "speed": 10,
                       "max_hp": 290, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 14},
        "level_scale_percent": 4,
        "max_poise": 12,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge"),
            get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    # ==================================================================
    # ROSTER EXPANSION.
    #
    # Twenty templates added in one pass, all of them built around a
    # SHAPE rather than a stat spread -- the roster's real problem wasn't
    # its size, it was that most encounters played identically once you'd
    # seen them. Each of these does something a player has to answer
    # differently: a glass cannon that must be killed this turn, a taunt
    # wall that can't be ignored, a structure with no speed and enormous
    # poise, a slow single-target hammer you break or eat.
    #
    # STRUCTURES (Revengeance Block, billboard, spy camera) share a
    # deliberate profile: speed near zero, huge or tiny poise, and no
    # ultimate. They're objects, and they should feel like objects.
    # ==================================================================
    {
        # A person very loudly insisting they are an AI. Fights like
        # someone who has read about fighting.
        "name": "MianotAI",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 23, "defense": 10, "elemental": 19, "speed": 12,
            "max_hp": 165, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 20,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "jamming_array"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        "name": "Entrospire Soldier",
        "role": "combat",
        "regions": ['The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 13, "defense": 6, "elemental": 4, "speed": 9,
            "max_hp": 44, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 14,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "power_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "rallying_plate")],
    },
    {
        # Requested as a boss. A duelist: few, enormous, precise strikes,
        # and a counter-attack passive that punishes trading with him.
        "name": "Samuel",
        "role": "boss",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "region_roles": {"The Hotlands": "regular"},
        "actions_per_cycle": 2,
        "base_stats": {
            "attack": 26, "defense": 9, "elemental": 6, "speed": 19,
            "max_hp": 265, "max_mana": 999, "crit_rate": 20, "crit_damage": 210, "recharge": 16,
        },
        "level_scale_percent": 4,
        "max_poise": 16,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "seven_cuts"),
            get_ability_by_id(WEAPON_SKILLS, "mercy_stroke"),
            get_ability_by_id(WEAPON_SKILLS, "riposte_chain"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "storm_of_blades"),
    },
    {
        # "Weak enemy with massive damage potential", as requested. 12 HP
        # and no defence at all, paired with the highest attack of any
        # non-boss on the roster: it dies to a stiff breeze and deletes a
        # squad member if you let it act. The whole encounter is "kill it
        # first", which is a decision, and the telegraph panel is what
        # makes that decision fair.
        "name": "67",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 67, "defense": 1, "elemental": 40, "speed": 21,
            "max_hp": 12, "max_mana": 999, "crit_rate": 30, "crit_damage": 150, "recharge": 30,
        },
        "level_scale_percent": 4,
        "max_poise": 2,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "desperate_swing")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
    },
    {
        # Ragebaiter. Requested with big health and defence AND a taunt --
        # provoking_aura forces your single-target attacks onto him, so
        # the answer is AOE (which ignores taunt) or breaking him.
        "name": "Kiradmj",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 11, "defense": 22, "elemental": 5, "speed": 7,
            "max_hp": 190, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 12,
        },
        "level_scale_percent": 4,
        "max_poise": 14,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge"),
            get_ability_by_id(WEAPON_SKILLS, "bulwark_slam"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "provoking_aura"),
            get_ability_by_id(ARMOR_PASSIVES, "reinforced_barrier"),
        ],
    },
    {
        # A structure. No speed to speak of, no ultimate, and enormous
        # poise -- you cannot break it out of its wind-up the way you can
        # a person, so the answer is to out-damage it or guard through it.
        "name": "The Revengeance Block",
        "role": "elite",
        "regions": ['Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 21, "defense": 26, "elemental": 14, "speed": 3,
            "max_hp": 230, "max_mana": 999, "crit_rate": 2, "crit_damage": 150, "recharge": 8,
        },
        "level_scale_percent": 4,
        "max_poise": 30,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
            get_ability_by_id(ARTIFACT_SKILLS, "kinetic_feedback"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "spiked_carapace")],
    },
    {
        "name": "Alan",
        "role": "elite",
        "regions": ['Glacier 15', 'The Hotlands'],
        "base_stats": {
            "attack": 18, "defense": 9, "elemental": 8, "speed": 14,
            "max_hp": 92, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sunder_the_weak"),
            get_ability_by_id(ARTIFACT_SKILLS, "hunters_mark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "opportunists_lens")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    {
        # Caliper's rogue creation. Acts three times a cycle and repairs
        # itself -- the fight is a race against its own maintenance.
        "name": "Bt03",
        "role": "boss",
        "regions": ['Glacier 15', 'Voidcrest Desert'],
        "actions_per_cycle": 3,
        "base_stats": {
            "attack": 19, "defense": 13, "elemental": 17, "speed": 17,
            "max_hp": 300, "max_mana": 999, "crit_rate": 9, "crit_damage": 175, "recharge": 20,
        },
        "level_scale_percent": 4,
        "max_poise": 18,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "overclock_repair"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(WEAPON_SKILLS, "twin_fracture_strike"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        # Thorns and mysterious substances, as specified. Hitting it is
        # the problem: thornmail plus spiked carapace means a multi-hit
        # squad shreds itself on it.
        "name": "Romain's Body Pillow",
        "role": "combat",
        "regions": ['The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 8, "defense": 16, "elemental": 9, "speed": 5,
            "max_hp": 70, "max_mana": 999, "crit_rate": 2, "crit_damage": 140, "recharge": 10,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "creeping_rot")],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "thornmail"),
            get_ability_by_id(ARMOR_PASSIVES, "spiked_carapace"),
        ],
    },
    {
        "name": "Xender Convoy",
        "role": "elite",
        "regions": ['The Wastelands', 'Voidcrest Desert'],
        "actions_per_cycle": 2,
        "base_stats": {
            "attack": 16, "defense": 18, "elemental": 6, "speed": 8,
            "max_hp": 175, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 14,
        },
        "level_scale_percent": 4,
        "max_poise": 16,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
            get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "bulwark_protocol")],
    },
    {
        "name": "Jynxzi",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "actions_per_cycle": 2,
        "base_stats": {
            "attack": 20, "defense": 8, "elemental": 10, "speed": 20,
            "max_hp": 105, "max_mana": 999, "crit_rate": 22, "crit_damage": 185, "recharge": 26,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "quickdraw_slash"),
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "battle_rhythm")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "gale_ascendant"),
    },
    {
        "name": "Xender Airship",
        "role": "elite",
        "regions": ['The Hotlands', 'Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 22, "defense": 12, "elemental": 18, "speed": 11,
            "max_hp": 160, "max_mana": 999, "crit_rate": 7, "crit_damage": 165, "recharge": 16,
        },
        "level_scale_percent": 4,
        "max_poise": 13,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),
            get_ability_by_id(ARTIFACT_SKILLS, "meteor_shower"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "focused_lens")],
    },
    {
        "name": "HHyper Airship",
        "role": "elite",
        "regions": ['Voidcrest Desert', 'Abyssnia'],
        "base_stats": {
            "attack": 25, "defense": 14, "elemental": 21, "speed": 13,
            "max_hp": 185, "max_mana": 999, "crit_rate": 9, "crit_damage": 170, "recharge": 18,
        },
        "level_scale_percent": 4,
        "max_poise": 13,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
            get_ability_by_id(ARTIFACT_SKILLS, "overcharged_bolt"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "static_discharge")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    {
        # A structure that fights with debuffs rather than damage -- it
        # barely hurts you, it just makes everything else hurt more.
        # Ignoring it is a mistake; it is also the lowest-priority target
        # on the field, which is the tension.
        "name": "False Advertising Billboard",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands'],
        "base_stats": {
            "attack": 6, "defense": 12, "elemental": 12, "speed": 2,
            "max_hp": 58, "max_mana": 999, "crit_rate": 1, "crit_damage": 130, "recharge": 10,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "corrosive_mark"),
            get_ability_by_id(ARTIFACT_SKILLS, "blight_cloud"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "plaguebearers_totem")],
    },
    {
        "name": "Xender Aerial Soldier",
        "role": "combat",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 15, "defense": 6, "elemental": 8, "speed": 16,
            "max_hp": 40, "max_mana": 999, "crit_rate": 10, "crit_damage": 160, "recharge": 20,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "opportunist_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "accelerant_coating")],
    },
    {
        "name": "Josh Hater",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 14, "defense": 7, "elemental": 5, "speed": 11,
            "max_hp": 48, "max_mana": 999, "crit_rate": 8, "crit_damage": 155, "recharge": 16,
        },
        "level_scale_percent": 4,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "gutting_thrust")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "grim_resolve")],
    },
    {
        "name": "Refense Hater",
        "role": "elite",
        "regions": ['The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 19, "defense": 11, "elemental": 9, "speed": 13,
            "max_hp": 112, "max_mana": 999, "crit_rate": 13, "crit_damage": 175, "recharge": 18,
        },
        "level_scale_percent": 4,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_scanner"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "guard_breaker")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Requested as an EXTREMELY difficult final boss and raid boss.
        # The hardest template in the file by a clear margin: four actions
        # a cycle, the highest poise on the roster, and a kit that both
        # denies turns and out-scales a long fight.
        "name": "Rohan",
        "role": "boss",
        "regions": ['Abyssnia'],
        "region_roles": {"Abyssnia": "final"},
        "actions_per_cycle": 4,
        "base_stats": {
            "attack": 44, "defense": 32, "elemental": 34, "speed": 26,
            "max_hp": 9999, "max_mana": 999, "crit_rate": 24, "crit_damage": 220, "recharge": 24,
        },
        "level_scale_percent": 5,
        "max_poise": 34,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "cataclysms_edge"),
            get_ability_by_id(WEAPON_SKILLS, "apex_predator"),
            get_ability_by_id(ARTIFACT_SKILLS, "astral_cascade"),
            get_ability_by_id(ARTIFACT_SKILLS, "overmind_surge"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "undying_will"),
            get_ability_by_id(ARMOR_PASSIVES, "momentum_core"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    {
        # Requested: single target, very hard hitting, but slow. Speed 4
        # against a party averaging 11 means it acts roughly once for
        # every two of your turns -- long enough to see the hit coming and
        # do something about it, which is the entire encounter.
        "name": "Frostblock",
        "role": "elite",
        "regions": ['Glacier 15', 'Abyssnia'],
        "base_stats": {
            "attack": 38, "defense": 17, "elemental": 24, "speed": 4,
            "max_hp": 200, "max_mana": 999, "crit_rate": 6, "crit_damage": 200, "recharge": 12,
        },
        "level_scale_percent": 4,
        "max_poise": 15,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "glacier_cleaver"),
            get_ability_by_id(ARTIFACT_SKILLS, "absolute_zero"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # Tiny, fragile, and entirely about marking someone for everything
        # else in the room to hit harder.
        "name": "Xender Spy Camera",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 4, "defense": 4, "elemental": 6, "speed": 18,
            "max_hp": 18, "max_mana": 999, "crit_rate": 2, "crit_damage": 130, "recharge": 22,
        },
        "level_scale_percent": 4,
        "max_poise": 3,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_marker")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "focused_lens")],
    },
    # ==================================================================
    # THE JOSH HATER ARMY -- a five-body boss group.
    #
    # All five are role="boss_group_member", so they're never rolled
    # independently as a combat/elite/boss encounter; they exist only as
    # this group (see BOSS_GROUPS below). That's what lets each one be
    # individually weak -- the fight's difficulty is the NUMBER of them
    # and how their jobs overlap, not any single statline.
    #
    # Five distinct jobs rather than five copies, because a five-enemy
    # fight against one repeated template is just one enemy with more HP
    # and a longer turn order. Here the party has an actual target-
    # priority problem: the Ringleader taunts so your single-target
    # damage can't reach anyone else, the Chant Leader makes the whole
    # group hit harder every turn it lives, and the Quiet Hater is the
    # one that will actually kill somebody. AOE (which ignores taunt) and
    # breaking the Ringleader are both real answers.
    # ==================================================================
    {
        # The loudest one. Taunts, and is built to survive doing it.
        "name": "Josh Hater Ringleader",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 14, "defense": 24, "elemental": 5, "speed": 8,
            "max_hp": 235, "max_mana": 999, "crit_rate": 3, "crit_damage": 140, "recharge": 12,
        },
        "level_scale_percent": 4,
        "max_poise": 12,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "guardian_challenge"),
            get_ability_by_id(WEAPON_SKILLS, "bulwark_slam"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "provoking_aura"),
            get_ability_by_id(ARMOR_PASSIVES, "reinforced_barrier"),
        ],
    },
    {
        # Buffs the other four. Left alive too long, the whole army
        # becomes a real problem -- this is the kill-order puzzle.
        "name": "Chant Leader",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 9, "defense": 11, "elemental": 6, "speed": 15,
            "max_hp": 75, "max_mana": 999, "crit_rate": 4, "crit_damage": 145, "recharge": 22,
        },
        "level_scale_percent": 4,
        "max_poise": 7,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rally_standard"),
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "warcallers_horn")],
    },
    {
        # Debuffs. Doesn't hurt you; makes everything else hurt more.
        "name": "Placard Bearer",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 10, "defense": 13, "elemental": 10, "speed": 10,
            "max_hp": 115, "max_mana": 999, "crit_rate": 3, "crit_damage": 140, "recharge": 16,
        },
        "level_scale_percent": 4,
        "max_poise": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "corrosive_mark"),
            get_ability_by_id(ARTIFACT_SKILLS, "weakpoint_scanner"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "plaguebearers_totem")],
    },
    {
        # Hits everyone at once for a little. Chip damage that adds up
        # while you're busy with the taunt wall.
        "name": "Megaphone Guy",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 15, "defense": 9, "elemental": 13, "speed": 12,
            "max_hp": 60, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 18,
        },
        "level_scale_percent": 4,
        "max_poise": 7,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sweeping_volley"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "focused_lens")],
    },
    {
        # Hasn't said a word. Will delete a squad member. The joke is
        # that the dangerous one is the one not shouting, and the
        # telegraph panel is what makes that discoverable rather than
        # unfair.
        "name": "The Quiet Hater",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 33, "defense": 8, "elemental": 24, "speed": 17,
            "max_hp": 52, "max_mana": 999, "crit_rate": 22, "crit_damage": 205, "recharge": 20,
        },
        "level_scale_percent": 4,
        "max_poise": 6,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "mercy_stroke"),
            get_ability_by_id(WEAPON_SKILLS, "gutting_thrust"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    # ==================================================================
    # DORVE -- Xender's elite assistant, in a giant mech.
    #
    # Built as an ESCORTED boss (see the "escorts" pass in the module
    # docstring) rather than one enormous statline, because a giant mech
    # that is mechanically identical to a large man is a wasted premise.
    # The gunpods are separate bodies with their own turns: you can shoot
    # them off, and doing so measurably reduces the incoming damage, so
    # the fight has a shape beyond "hit the boss".
    #
    # Sits just under Xender himself -- he's the assistant, and the
    # numbers should say so.
    # ==================================================================
    {
        "name": "Dorve",
        "role": "boss",
        "region_roles": {"Voidcrest Desert": "regular", "Abyssnia": "regular"},
        "actions_per_cycle": 3,
        "escorts": ["Mech Gunpod", "Mech Gunpod"],
        "base_stats": {
            "attack": 47, "defense": 20, "elemental": 25, "speed": 18,
            "max_hp": 495, "max_mana": 999, "crit_rate": 15, "crit_damage": 195, "recharge": 20,
        },
        "level_scale_percent": 4,
        "max_poise": 26,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
            get_ability_by_id(ARTIFACT_SKILLS, "meteor_shower"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(ARTIFACT_SKILLS, "rallying_bulwark"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "bulwark_protocol"),
            get_ability_by_id(ARMOR_PASSIVES, "adaptive_plating"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Hardpoint on Dorve's mech. Fragile on purpose -- destroying one
        # is meant to be an achievable, visibly worthwhile decision
        # mid-fight rather than a second health bar.
        "name": "Mech Gunpod",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 20, "defense": 10, "elemental": 16, "speed": 13,
            "max_hp": 72, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 18,
        },
        "level_scale_percent": 4,
        "max_poise": 6,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "crossfire_salvo"),
            get_ability_by_id(ARTIFACT_SKILLS, "overcharged_bolt"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "focused_lens")],
    },
]

# Named multi-enemy boss encounters. Each entry is a list of template names
# (looked up live from ENEMY_TEMPLATES, so edits to the roster above stay
# in sync) that all appear together in a single BOSS-room fight, in place
# of the usual single boss template.
BOSS_GROUPS: dict[str, list[str]] = {
    "eruptor_trio": ["Borehole", "Rupture", "Gatekeeper"],
    "acatrya_board": ["Exiled Acid", "Exiled APS", "Exiled JP"],
    # Five bodies -- the largest group in the game, and the only one where
    # the difficulty is target priority rather than raw statlines.
    "josh_hater_army": [
        "Josh Hater Ringleader", "Chant Leader", "Placard Bearer",
        "Megaphone Guy", "The Quiet Hater",
    ],
}

# Same idea as a solo boss template's "region_roles" field (see
# ENEMY_TEMPLATES above): which region(s) this group can show up in, and
# whether it counts as a "regular" checkpoint boss or reserved for that
# region's FINAL boss there.
BOSS_GROUP_REGION_ROLES: dict[str, dict[str, str]] = {
    "eruptor_trio": {"Voidcrest Desert": "final"},
    "acatrya_board": {"Abyssnia": "regular"},
    # A checkpoint boss in the two regions Josh is most disliked in,
    # rather than a final -- it's a set-piece, not a wall.
    "josh_hater_army": {"Glacier 15": "regular", "The Wastelands": "regular"},
}

# Chance that a BOSS room rolls one of the eligible BOSS_GROUPS instead of
# a single solo "boss"-role template. Kept low -- these are meant to be
# rare, harder set-piece fights, not the default boss encounter.
BOSS_GROUP_CHANCE = 0.2


def get_templates_by_role(role: str, region: str | None = None) -> list[dict]:
    """All templates for a role, optionally narrowed to ones eligible for
    `region` (via each template's "regions" field -- combat/elite -- or
    "region_roles" field -- boss). If narrowing to a region leaves nothing
    (shouldn't happen given the roster's region coverage, but content gaps
    are easy to introduce by accident), falls back to the full, unfiltered
    role pool rather than crash or return an empty combat encounter."""
    templates = [t for t in ENEMY_TEMPLATES if t["role"] == role]
    if region is None:
        return templates
    if role == "boss":
        narrowed = [t for t in templates if region in t.get("region_roles", {})]
    else:
        narrowed = [t for t in templates if region in t.get("regions", [])]
    return narrowed or templates


def get_template_by_name(name: str) -> dict:
    for template in ENEMY_TEMPLATES:
        if template["name"] == name:
            return template
    raise KeyError(f"No enemy template named {name!r}")


def _with_escorts(template: dict) -> list[dict]:
    """Some solo "boss"-role templates always fight alongside fixed
    companion enemies (that template's "escorts" field, a list of names --
    see the module docstring's "Multi-enemy bosses" section). Escorts are
    boss_group_member-role templates that are never independently rolled;
    they're looked up by name here and appended so the boss room fields
    every one of them alongside the named boss, every time it's chosen."""
    encounter = [template]
    for escort_name in template.get("escorts", []):
        encounter.append(get_template_by_name(escort_name))
    return encounter


def get_boss_encounter(
    rng: random.Random | None = None, region: str | None = None, final: bool = False
) -> list[dict]:
    """Returns the list of enemy template(s) for a BOSS room: usually a
    single random "boss"-role template, occasionally (BOSS_GROUP_CHANCE)
    one of the named BOSS_GROUPS fought together instead.

    `region` narrows candidates to that region's roster; `final=True`
    narrows further to templates/groups whose region_roles designates them
    as that region's FINAL boss (reserved for the last boss node of a run
    -- see dungeon_service.enter_node), rather than an earlier checkpoint
    boss. If a region has no dedicated candidates for the requested
    role (regular/final), this widens step by step -- same role in any
    region, then any boss at all -- instead of crashing."""
    rng = rng or random.Random()
    role = "final" if final else "regular"

    def _solo_candidates(strict: bool) -> list[dict]:
        solo = get_templates_by_role("boss")
        if region is None:
            return solo
        if strict:
            return [t for t in solo if t.get("region_roles", {}).get(region) == role]
        return [t for t in solo if role in t.get("region_roles", {}).values()]

    def _group_candidates(strict: bool) -> list[str]:
        if region is None:
            return list(BOSS_GROUP_REGION_ROLES.keys())
        if strict:
            return [g for g, roles in BOSS_GROUP_REGION_ROLES.items() if roles.get(region) == role]
        return [g for g, roles in BOSS_GROUP_REGION_ROLES.items() if role in roles.values()]

    solo_strict, group_strict = _solo_candidates(strict=True), _group_candidates(strict=True)
    if solo_strict or group_strict:
        # This exact region+role combination has real candidates -- use
        # only those, so e.g. Glacier 15's final boss never accidentally
        # pulls in a group that's only meant for Wastelands/Voidcrest.
        solo_candidates, group_candidates = solo_strict, group_strict
    else:
        # No dedicated content for this region+role -- widen step by step
        # (same role anywhere, then any boss at all) rather than crash.
        solo_candidates = _solo_candidates(strict=False) or get_templates_by_role("boss")
        group_candidates = _group_candidates(strict=False)

    # Bugfix (surfaced by the escorts pass, but pre-existing): a
    # region+role combination can have group candidates and NO solo
    # candidates at all (e.g. Voidcrest Desert's final boss used to be
    # solo-less, group-only via the Eruptor Trio). In that case a group
    # MUST be used -- falling through to rng.choice(solo_candidates) below
    # would crash on an empty list roughly (1 - BOSS_GROUP_CHANCE) of the
    # time.
    if group_candidates and (not solo_candidates or rng.random() < BOSS_GROUP_CHANCE):
        group_name = rng.choice(group_candidates)
        return [get_template_by_name(n) for n in BOSS_GROUPS[group_name]]

    return _with_escorts(rng.choice(solo_candidates))


# ----------------------------------------------------------------------
# SHORT NAMES for width-limited views (turn order, telegraph lines).
#
# Kept as a lookup here rather than a key on each template so the roster
# above stays readable, and so this reads as what it is: a display
# concern, not a property of the enemy.
#
# Every entry drops the FACTION or QUALIFIER and keeps the distinctive
# noun, because that's the part that tells two enemies apart. Automatic
# shortening was tried first and produced "Glacial", "Permafrost" for two
# DIFFERENT enemies, and "Lector of" -- which is exactly the ambiguity a
# name is supposed to prevent. Where the automatic result was already
# good it's simply written down here, so the rule is "look it up", with
# no second guess about which names are handled and which aren't.
#
# tools/check_ui_labels.py asserts that every name longer than the turn
# order budget has an entry, that no entry EXCEEDS that budget, and that
# no two entries collide -- so this can't silently rot as the roster
# grows.
# ----------------------------------------------------------------------
ENEMY_SHORT_NAMES: dict[str, str] = {
    "Boss John's Driller Prototype": "Driller Proto.",
    "Wasteland Colosseum Champion": "Colosseum Champ",
    "Propaganda Broadcast Unit": "Broadcast Unit",
    "Ocellios Failed Prototype": "Failed Proto.",
    "Xendium Overcharge Drone": "Overcharge Drone",
    "Corporate Security Mech": "Security Mech",
    "H-Nation Border Trooper": "Border Trooper",
    "Entropy Aura Generator": "Aura Generator",
    "Acatrya Prime Enforcer": "Prime Enforcer",
    "Tower Maintenance Bot": "Maintenance Bot",
    "Corrupted Eris Sentry": "Eris Sentry",
    "Corrupted Wastelander": "Wastelander",
    "Sacrificial Construct": "Sacr. Construct",
    "Ocellios Test Subject": "Test Subject",
    "The Lector of Ledgers": "The Lector",
    "Rogue Security Drone": "Security Drone",
    "Glacial Exterminator": "Glacial Exterm.",
    "Permafrost Automaton": "Frost Automaton",
    "Xender Command Relay": "Command Relay",
    "Acatrya Riot Trooper": "Riot Trooper",
    "Acatrya Field Medic": "Field Medic",
    "Undercity Scavenger": "Scavenger",
    "Ad-Drone Swarm Unit": "Ad-Drone Swarm",
    "Xendium Lab Soldier": "Lab Soldier",
    "Acatrya Elite Guard": "Elite Guard",
    "Permafrost Guardian": "Frost Guardian",
    "Voidcrest Skitterer": "Skitterer",
    "Voidwarp Construct": "Voidwarp Const.",
    "Cinderveil Acolyte": "Acolyte",
    "Voidcell Amplifier": "Voidcell Amp.",
    "Skybridge Sentinel": "Sentinel",
    "Xender Recon Scout": "Recon Scout",
    "Abyssal Custodian": "Custodian",
    "Blightspire Adept": "Adept",
    "H-Nation Vanguard": "Vanguard",
    "Wastes Fieldmedic": "Fieldmedic",
    "Nullwrit Enforcer": "Enforcer",
    "XG-23 Heavy Drone": "XG-23 Heavy",
    "Shatterjaw Reaver": "Reaver",
    "Duneglass Stalker": "Stalker",
    "Stubby's Failsafe": "Failsafe",
    "Wandering Vagrant": "Vagrant",
    # --- roster expansion ---
    "False Advertising Billboard": "Ad Billboard",
    "Xender Aerial Soldier": "Aerial Soldier",
    "The Revengeance Block": "Revenge Block",
    "Romain's Body Pillow": "Body Pillow",
    "Entrospire Soldier": "Entrospire Sol.",
    "Xender Spy Camera": "Spy Camera",
}


def short_name_for(name: str) -> str:
    """The display name to use where width is tight. Falls back to the
    full name, which is correct for the 49 templates already short
    enough to need no entry."""
    return ENEMY_SHORT_NAMES.get(name, name)
