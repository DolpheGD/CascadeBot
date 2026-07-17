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
  * "combat" -- regular room enemies, 1-2 per fight.
  * "elite"  -- elite rooms, 1 per fight, meaningfully tougher.
  * "boss"   -- standalone boss-room enemies, 1 per fight.
  * "boss_group_member" -- boss-room enemies that only ever appear together
    as part of a BOSS_GROUPS entry (see get_boss_encounter()), never rolled
    individually via get_templates_by_role("boss").

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
            "max_hp": 32, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 6,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "quickdraw_slash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "scrap_armor")],
    },
    {
        # Rank-and-file Xender muscle -- crowd control batons, standard
        # issue armor. Seen wherever Acatrya projects authority.
        "name": "Xender Henchmen",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 12, "defense": 5, "elemental": 3, "speed": 8,
            "max_hp": 42, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 6,
        },
        "level_scale_percent": 8,
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
            "max_hp": 52, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 7,
        },
        "level_scale_percent": 8,
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
            "attack": 100, "defense": 1, "elemental": 5, "speed": 1,
            "max_hp": 1, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 70,
        },
        "level_scale_percent": 8,
        "active_abilities": [],
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
            "max_hp": 58, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 60, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 48, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 30, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 8,
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
            "max_hp": 45, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 65, "max_mana": 999, "crit_rate": 3, "crit_damage": 150, "recharge": 10,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        # Abyssnia crowd control -- networked units that share
        # battlefield data, so putting one down feeds the others.
        "name": "Acatrya Riot Trooper",
        "role": "combat",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 13, "defense": 8, "elemental": 3, "speed": 7,
            "max_hp": 50, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 38, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 44, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
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
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands'],
        "base_stats": {
            "attack": 4, "defense": 6, "elemental": 5, "speed": 8,
            "max_hp": 65, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 16,
        },
        "level_scale_percent": 8,
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
            "max_hp": 60, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 15,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
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
            "max_hp": 55, "max_mana": 999, "crit_rate": 3, "crit_damage": 145, "recharge": 4,
        },
        "level_scale_percent": 8,
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
            "max_hp": 40, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 5,
        },
        "level_scale_percent": 8,
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
            "max_hp": 76, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [],
    },
    {
        # Voidcrest's second combat-tier enemy
        "name": "Entropy Executor",
        "role": "combat",
        "regions": ['The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 8, "defense": 12, "elemental": 24, "speed": 13,
            "max_hp": 78, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 6,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst")],
        "passive_abilities": [],
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
            "max_hp": 60, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 5,
        },
        "level_scale_percent": 8,
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
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "void_grasp")],
        "passive_abilities": [],
    },
    # ---------------------------------------------------------------
    # ELITE -- tougher, 1-per-fight encounters
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
            "max_hp": 140, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 8,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
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
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 12, "defense": 14, "elemental": 22, "speed": 9,
            "max_hp": 130, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "last_stand"),
    },
    {
        # A grifter who's built a whole act around impersonating Dolphe
        # to shake down towns Team Cascade hasn't reached yet -- all
        # showmanship, no substance, but the crowd-hyped tricks land
        # hard enough to hurt.
        # Balance pass: the roster's single fastest combatant (Speed 20),
        # so it's the elite-tier "acts twice a cycle" pick -- ATK/ELE
        # pulled down to compensate for the extra action.
        "name": "Dolpo",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 8, "defense": 8, "elemental": 9, "speed": 20,
            "max_hp": 100, "max_mana": 999, "crit_rate": 15, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 10,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(WEAPON_SKILLS, "berserker_rage"),
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
            "max_hp": 180, "max_mana": 999, "crit_rate": 14, "crit_damage": 180, "recharge": 9,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
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
            "max_hp": 135, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 10,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "soul_siphon"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "second_wind")],
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
            "max_hp": 125, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 9,
        },
        "level_scale_percent": 10,
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
            "max_hp": 160, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 7,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
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
            "attack": 13, "defense": 23, "elemental": 12, "speed": 6,
            "max_hp": 175, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "sunder_strike"),
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
            "max_hp": 220, "max_mana": 999, "crit_rate": 12, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 10,
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
        # Voidcrest Desert had 4 elites and every one of them was shared
        # with The Hotlands -- nothing gave the hardest region its own
        # identity at elite tier. A larger, more coherent fragment of
        # Void-matter than the Entropy Wisps, the closest thing Voidcrest
        # has to a native apex predator rather than an invading faction.
        # Balance pass: high Speed, near-zero DEF -- a fast glass cannon,
        # so it gets Arc Lightning (the light AoE option) rather than a
        # heavy one. Also the roster's fastest elite after Dolpo, so it
        # now joins Dolpo as a "acts twice a cycle" pick -- ATK/ELE pulled
        # down ~20% to compensate, same ratio used everywhere else.
        "name": "Sir Vengeance",
        "role": "elite",
        "regions": ['Glacier 15', 'The Wastelands', 'The Hotlands', 'Voidcrest Desert'],
        "base_stats": {
            "attack": 15, "defense": 2, "elemental": 2, "speed": 23,
            "max_hp": 270, "max_mana": 999, "crit_rate": 10, "crit_damage": 280, "recharge": 10,
        },
        "level_scale_percent": 10,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "arc_lightning"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "gale_ascendant"),
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
        "name": "XG-23 Heavy Drone",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Wastelands': 'regular', 'The Hotlands': 'regular'},
        "base_stats": {
            "attack": 24, "defense": 10, "elemental": 10, "speed": 14,
            "max_hp": 270, "max_mana": 999, "crit_rate": 14, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 8,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "kinetic_feedback"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "storm_of_blades"),
    },
    {
        # regular boss for all areas
        # Balance pass: slow (Speed 8) and by far the tankiest regular
        # boss (670 base HP) -- the "slow, hard-hitting" AoE profile, so
        # it picks up Cleave Smash alongside its support kit.
        "name": "Boss John's Driller Prototype",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Wastelands': 'regular', 'The Hotlands': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 29, "defense": 12, "elemental": 12, "speed": 8,
            "max_hp": 670, "max_mana": 999, "crit_rate": 9, "crit_damage": 190, "recharge": 10,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "overclock_repair"),
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(WEAPON_SKILLS, "cleave_smash"),
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
            "attack": 14, "defense": 8, "elemental": 24, "speed": 14,
            "max_hp": 350, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 6,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "null_strike"),
    },
    {
        # HHyper ship, the first of its kind deployed to the region
        "name": "Aerion Mk1",
        "role": "boss",
        "region_roles": {'The Hotlands': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 34, "defense": 10, "elemental": 25, "speed": 10,
            "max_hp": 430, "max_mana": 999, "crit_rate": 13, "crit_damage": 175, "recharge": 10,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "guard_splitter"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "executioner")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
    },
    {
        # HHyper's Elite Unit -- a corrupted version of the standard Bli design
        # Balance pass: the fastest non-XG-23 boss (Speed 16) -- the
        # roster's other multi-action pick, with attack/elemental pulled
        # down to compensate for the extra action per cycle.
        "name": "Corrupted Bli",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'Voidcrest Desert': 'regular'},
        "base_stats": {
            "attack": 7, "defense": 8, "elemental": 11, "speed": 22,
            "max_hp": 400, "max_mana": 999, "crit_rate": 6, "crit_damage": 180, "recharge": 12,
        },
        "level_scale_percent": 8,
        "actions_per_cycle": 3,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "riftcutter"),
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Same gap in The Hotlands -- Cinderclad Devastator was the only
        # final boss there. Ocellios Labs' ultimate failed experiment,
        # escalated far past the Test Subject elite and the Failed
        # Prototype grunts, offered as a second final-tier option.
        "name": "Thedoggyp",
        "role": "boss",
        "region_roles": {'Glacier 15': 'regular', 'The Wastelands': 'regular', 'The Hotlands': 'regular'},
        "base_stats": {
            "attack": 18, "defense": 11, "elemental": 10, "speed": 10,
            "max_hp": 300, "max_mana": 999, "crit_rate": 2, "crit_damage": 500, "recharge": 12,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "soul_harvest")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
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
        "name": "Void Hydra",
        "role": "boss",
        "region_roles": {'Glacier 15': 'final'},
        "base_stats": {
            "attack": 23, "defense": 8, "elemental": 26, "speed": 11,
            "max_hp": 420, "max_mana": 999, "crit_rate": 16, "crit_damage": 185, "recharge": 10,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "ionic_ward"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "vampiric_edge")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "world_ender"),
    },
    {
        # The Negadom (Josh's creation that went wrong)
        "name": "The Negadom",
        "role": "boss",
        "region_roles": {'The Wastelands': 'final'},
        "base_stats": {
            "attack": 33, "defense": 14, "elemental": 33, "speed": 9,
            "max_hp": 540, "max_mana": 999, "crit_rate": 11, "crit_damage": 170, "recharge": 15,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "aegis_broadcast"),
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
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
            "attack": 36, "defense": 12, "elemental": 20, "speed": 13,
            "max_hp": 650, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 14,
        },
        "level_scale_percent": 8,
        "actions_per_cycle": 2,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
            get_ability_by_id(ARMOR_PASSIVES, "capacitor_shell"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
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
            "max_hp": 430, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 6,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "thornmail"),
            get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating"),
        ],
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
            "max_hp": 370, "max_mana": 999, "crit_rate": 14, "crit_damage": 175, "recharge": 7,
        },
        "actions_per_cycle": 2,
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
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
            "max_hp": 580, "max_mana": 999, "crit_rate": 50, "crit_damage": 120, "recharge": 8,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "aegis_broadcast"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "meteor_shower"),
        ],
        "passive_abilities": [
            get_ability_by_id(ARMOR_PASSIVES, "iron_skin"),
            get_ability_by_id(ARMOR_PASSIVES, "regen_field_generator"),
        ],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
]

# Named multi-enemy boss encounters. Each entry is a list of template names
# (looked up live from ENEMY_TEMPLATES, so edits to the roster above stay
# in sync) that all appear together in a single BOSS-room fight, in place
# of the usual single boss template.
BOSS_GROUPS: dict[str, list[str]] = {
    "eruptor_trio": ["Borehole", "Rupture", "Gatekeeper"],
}

# Same idea as a solo boss template's "region_roles" field (see
# ENEMY_TEMPLATES above): which region(s) this group can show up in, and
# whether it counts as a "regular" checkpoint boss or reserved for that
# region's FINAL boss there.
BOSS_GROUP_REGION_ROLES: dict[str, dict[str, str]] = {
    "eruptor_trio": {"Voidcrest Desert": "final"},
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

    if group_candidates and rng.random() < BOSS_GROUP_CHANCE:
        group_name = rng.choice(group_candidates)
        return [get_template_by_name(n) for n in BOSS_GROUPS[group_name]]

    return [rng.choice(solo_candidates)]
