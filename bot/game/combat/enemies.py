"""
Enemy templates for combat. Deliberately reuse WEAPON_SKILLS / ARTIFACT_SKILLS
/ ULTIMATE_ABILITIES / ARMOR_PASSIVES from bot/game/loot/abilities.py rather
than a separate enemy-ability vocabulary -- an enemy "knowing Flame Strike"
and a weapon that grants Flame Strike are mechanically identical to the
combat engine, so one effect-resolution system covers both. Enemy resource
costs are irrelevant (they have effectively unlimited mana), but the
ultimate is still gated by energy reaching 100 so bosses don't nuke turn one.

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
        "base_stats": {
            "attack": 6, "defense": 3, "elemental": 1, "speed": 7,
            "max_hp": 32, "max_mana": 999, "crit_rate": 4, "crit_damage": 140, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "power_strike")],
        "passive_abilities": [],
    },
    {
        # Rank-and-file Xender muscle -- crowd control batons, standard
        # issue armor. Seen wherever Acatrya projects authority.
        "name": "Xender Henchmen",
        "role": "combat",
        "base_stats": {
            "attack": 8, "defense": 5, "elemental": 3, "speed": 8,
            "max_hp": 42, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [],
    },
    {
        # A step up from Henchmen -- carries incendiary rounds and
        # actually expects to see combat, not just crowd control.
        "name": "Xender Enforcer",
        "role": "combat",
        "base_stats": {
            "attack": 10, "defense": 7, "elemental": 5, "speed": 9,
            "max_hp": 52, "max_mana": 999, "crit_rate": 6, "crit_damage": 155, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [],
    },
    {
        # Glacier 15's "rogue security drones that never got the
        # shutdown order" -- still patrolling the ruin decades later.
        "name": "Rogue Security Drone",
        "role": "combat",
        "base_stats": {
            "attack": 7, "defense": 9, "elemental": 5, "speed": 6,
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
        "base_stats": {
            "attack": 9, "defense": 10, "elemental": 3, "speed": 5,
            "max_hp": 60, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "retaliation_plating")],
    },
    {
        # Glacier 15's cold-region counterpart to the Dune Digger -- a
        # drilling unit that never stopped clearing ice tunnels.
        "name": "Glacial Piercer",
        "role": "combat",
        "base_stats": {
            "attack": 8, "defense": 6, "elemental": 7, "speed": 8,
            "max_hp": 48, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "frost_lance")],
        "passive_abilities": [],
    },
    {
        # A stray, unstable munition off the Void Crevasse -- small,
        # fast, and prone to unpredictable elemental discharge.
        "name": "Voidcrest Skitterer",
        "role": "combat",
        "base_stats": {
            "attack": 7, "defense": 3, "elemental": 9, "speed": 12,
            "max_hp": 30, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "frost_lance")],
        "passive_abilities": [],
    },
    {
        # One of the Wastelands' "strikers and protestors" the advanced
        # world left behind -- fighting with improvised gear and real
        # anger, not a paycheck.
        "name": "Wasteland Striker",
        "role": "combat",
        "base_stats": {
            "attack": 11, "defense": 5, "elemental": 2, "speed": 9,
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
        "name": "Ash Turret",
        "role": "combat",
        "base_stats": {
            "attack": 9, "defense": 12, "elemental": 8, "speed": 3,
            "max_hp": 65, "max_mana": 999, "crit_rate": 3, "crit_damage": 150, "recharge": 4,
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
        "base_stats": {
            "attack": 9, "defense": 8, "elemental": 3, "speed": 7,
            "max_hp": 50, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "soul_harvest")],
    },
    {
        # A quadrupedal scrapper unit built to hunt down anything that
        # wanders too deep into contested salvage territory.
        "name": "Scrap Hound",
        "role": "combat",
        "base_stats": {
            "attack": 10, "defense": 4, "elemental": 2, "speed": 11,
            "max_hp": 38, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "phoenix_dive")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "vampiric_edge")],
    },
    {
        # A wastelander half-fused with malfunctioning salvage after too
        # long near a Void-poisoned site -- burns and freezes in the
        # same breath, and doesn't seem to notice either.
        "name": "Static-Choked Wanderer",
        "role": "combat",
        "base_stats": {
            "attack": 7, "defense": 5, "elemental": 8, "speed": 7,
            "max_hp": 44, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
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
        "base_stats": {
            "attack": 6, "defense": 6, "elemental": 8, "speed": 8,
            "max_hp": 45, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "combat_medic"),
            get_ability_by_id(ARTIFACT_SKILLS, "regenerative_field"),
            get_ability_by_id(ARTIFACT_SKILLS, "power_transfer"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "support_matrix")],
    },
    {
        # A coordination drone that doesn't fight so much as make
        # everything around it fight better -- broadcasts targeting data
        # to its own side and jamming static at the party's.
        "name": "Xender Command Relay",
        "role": "combat",
        "base_stats": {
            "attack": 7, "defense": 7, "elemental": 6, "speed": 7,
            "max_hp": 50, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "static_field"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    # ---------------------------------------------------------------
    # ELITE -- tougher, 1-per-fight encounters
    # ---------------------------------------------------------------
    {
        # Xender's answer to Team Cascade's better-equipped operatives --
        # slower, but built to shrug off small-arms fire.
        "name": "Xender Tank",
        "role": "elite",
        "base_stats": {
            "attack": 15, "defense": 18, "elemental": 6, "speed": 7,
            "max_hp": 140, "max_mana": 999, "crit_rate": 7, "crit_damage": 155, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        # An Eris-wreckage construct reactivated by leaking Void-matter --
        # not built by anyone still alive to ask about it.
        "name": "Voidwarp Construct",
        "role": "elite",
        "base_stats": {
            "attack": 12, "defense": 14, "elemental": 16, "speed": 9,
            "max_hp": 130, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(ARTIFACT_SKILLS, "emp_burst"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    {
        # A grifter who's built a whole act around impersonating Dolphe
        # to shake down towns Team Cascade hasn't reached yet -- all
        # showmanship, no substance, but the crowd-hyped tricks land
        # hard enough to hurt.
        "name": "Dolpo",
        "role": "elite",
        "base_stats": {
            "attack": 11, "defense": 8, "elemental": 15, "speed": 14,
            "max_hp": 100, "max_mana": 999, "crit_rate": 15, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 10,
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
        "base_stats": {
            "attack": 17, "defense": 12, "elemental": 5, "speed": 10,
            "max_hp": 120, "max_mana": 999, "crit_rate": 14, "crit_damage": 180, "recharge": 6,
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
        "base_stats": {
            "attack": 13, "defense": 9, "elemental": 18, "speed": 11,
            "max_hp": 125, "max_mana": 999, "crit_rate": 9, "crit_damage": 165, "recharge": 7,
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
        "base_stats": {
            "attack": 10, "defense": 10, "elemental": 20, "speed": 9,
            "max_hp": 115, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 9,
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
        "name": "Glacier 15 Custodian",
        "role": "elite",
        "base_stats": {
            "attack": 14, "defense": 16, "elemental": 10, "speed": 8,
            "max_hp": 150, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "shield_bash"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "executioners_reckoning"),
    },
    # ---------------------------------------------------------------
    # BOSS -- standalone, 1-per-fight
    # ---------------------------------------------------------------
    {
        # A Hotlands war-machine slagged and refused down to its core by
        # a Xendium reactor overload -- still walking, still armed.
        "name": "Cinderclad Devastator",
        "role": "boss",
        "base_stats": {
            "attack": 22, "defense": 12, "elemental": 24, "speed": 10,
            "max_hp": 260, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cataclysm"),
    },
    {
        # Acatrya's heavy air-superiority unit -- fast, well-armed, and
        # deployed wherever Xender wants a show of force from above.
        "name": "XG-23 Heavy Drone",
        "role": "boss",
        "base_stats": {
            "attack": 20, "defense": 14, "elemental": 20, "speed": 14,
            "max_hp": 240, "max_mana": 999, "crit_rate": 14, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(ARTIFACT_SKILLS, "system_purge"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        # A hijacked communications tower somewhere between Abyssnia and
        # the Wastelands -- once relayed The Daily Dolphe, now loops
        # whatever Xender wants broadcast, and defends itself when
        # Team Cascade comes to cut the signal.
        "name": "The Broadcast",
        "role": "boss",
        "base_stats": {
            "attack": 18, "defense": 14, "elemental": 26, "speed": 9,
            "max_hp": 250, "max_mana": 999, "crit_rate": 11, "crit_damage": 170, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "healing_light"),
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "arcane_battery")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "ascension"),
    },
    {
        # A name from the Ocellios files: "means nothing to the player
        # yet and everything to someone who survived it." Whatever it
        # was meant to become, this is what got loose.
        "name": "Subject 29",
        "role": "boss",
        "base_stats": {
            "attack": 16, "defense": 10, "elemental": 28, "speed": 12,
            "max_hp": 230, "max_mana": 999, "crit_rate": 16, "crit_damage": 185, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "soul_siphon"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "vampiric_edge")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "meteor_ultimate"),
    },
    {
        # An automated defense system built by Ocellios's reclusive
        # founder -- exactly as failsafe as the name promises. Very
        # rarely encountered, and built not to stay down.
        "name": "Stubby's Failsafe",
        "role": "boss",
        "base_stats": {
            "attack": 24, "defense": 18, "elemental": 18, "speed": 8,
            "max_hp": 280, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "rending_cleave"),
            get_ability_by_id(ARTIFACT_SKILLS, "overclock_repair"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "undying_will")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
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
            "attack": 18, "defense": 20, "elemental": 6, "speed": 5,
            "max_hp": 230, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 6,
        },
        "level_scale_percent": 10,
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
        "name": "Rupture",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 20, "defense": 10, "elemental": 22, "speed": 13,
            "max_hp": 170, "max_mana": 999, "crit_rate": 14, "crit_damage": 175, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "momentum")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "cascade_barrage"),
    },
    {
        # The Trio's brain: an oversized display rig that never leaves
        # the back of the chamber, directing every blaster and cannon
        # wired into it -- and, worse, actively coordinating with the
        # other two. Keeping this one alive keeps Borehole and Rupture
        # both hitting harder and patching themselves back up, which is
        # most of what makes this fight "very difficult."
        "name": "Gatekeeper",
        "role": "boss_group_member",
        "base_stats": {
            "attack": 12, "defense": 16, "elemental": 24, "speed": 8,
            "max_hp": 180, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 8,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "rousing_signal"),
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
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

# Chance that a BOSS room rolls one of BOSS_GROUPS instead of a single
# "boss"-role template. Kept low -- these are meant to be rare, harder
# set-piece fights, not the default boss encounter.
BOSS_GROUP_CHANCE = 0.2


def get_templates_by_role(role: str) -> list[dict]:
    return [t for t in ENEMY_TEMPLATES if t["role"] == role]


def get_template_by_name(name: str) -> dict:
    for template in ENEMY_TEMPLATES:
        if template["name"] == name:
            return template
    raise KeyError(f"No enemy template named {name!r}")


def get_boss_encounter(rng: random.Random | None = None) -> list[dict]:
    """Returns the list of enemy template(s) for a BOSS room: usually a
    single random "boss"-role template, occasionally (BOSS_GROUP_CHANCE)
    one of the named BOSS_GROUPS fought together instead."""
    rng = rng or random.Random()
    if BOSS_GROUPS and rng.random() < BOSS_GROUP_CHANCE:
        group_name = rng.choice(list(BOSS_GROUPS.keys()))
        return [get_template_by_name(n) for n in BOSS_GROUPS[group_name]]

    solo_bosses = get_templates_by_role("boss")
    return [rng.choice(solo_bosses)]
