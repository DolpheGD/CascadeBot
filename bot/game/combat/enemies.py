"""
Enemy templates for combat. Deliberately reuse WEAPON_SKILLS / ARTIFACT_SKILLS
/ ULTIMATE_ABILITIES / ARMOR_PASSIVES from bot/game/loot/abilities.py rather
than a separate enemy-ability vocabulary -- an enemy "knowing Flame Strike"
and a weapon that grants Flame Strike are mechanically identical to the
combat engine, so one effect-resolution system covers both. Enemy resource
costs are irrelevant (they have effectively unlimited mana), but the
ultimate is still gated by energy reaching 100 so bosses don't nuke turn one.

This is a small starter roster (one per room type: combat, elite, boss) to
prove the engine end-to-end. Expanding per-region content is a separate,
later content pass.
"""

from __future__ import annotations

from bot.game.loot.abilities import (
    ARMOR_PASSIVES,
    ARTIFACT_SKILLS,
    ULTIMATE_ABILITIES,
    WEAPON_SKILLS,
    get_ability_by_id,
)

ENEMY_TEMPLATES: list[dict] = [
    {
        "name": "Goblin",
        "role": "combat",
        "base_stats": {
            "attack": 8, "defense": 4, "elemental": 2, "speed": 8,
            "max_hp": 40, "max_mana": 999, "crit_rate": 5, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "shield_bash")],
        "passive_abilities": [],
    },
    {
        "name": "Poison Goblin",
        "role": "combat",
        "base_stats": {
            "attack": 9, "defense": 4, "elemental": 6, "speed": 9,
            "max_hp": 45, "max_mana": 999, "crit_rate": 6, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(WEAPON_SKILLS, "flame_strike")],
        "passive_abilities": [],
    },
    {
        "name": "Cascade Sentinel",
        "role": "combat",
        "base_stats": {
            "attack": 7, "defense": 8, "elemental": 4, "speed": 6,
            "max_hp": 55, "max_mana": 999, "crit_rate": 4, "crit_damage": 150, "recharge": 5,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(ARTIFACT_SKILLS, "arcane_burst")],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
    },
    {
        "name": "Elite Frenzied Poison Goblin",
        "role": "elite",
        "base_stats": {
            "attack": 16, "defense": 8, "elemental": 10, "speed": 11,
            "max_hp": 110, "max_mana": 999, "crit_rate": 10, "crit_damage": 165, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(WEAPON_SKILLS, "flame_strike"),
            get_ability_by_id(WEAPON_SKILLS, "berserker_rage"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "meteor_ultimate"),
    },
    {
        "name": "Voidwarp Construct",
        "role": "elite",
        "base_stats": {
            "attack": 12, "defense": 14, "elemental": 16, "speed": 9,
            "max_hp": 130, "max_mana": 999, "crit_rate": 8, "crit_damage": 160, "recharge": 6,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "void_grasp"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "thornmail")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
    {
        "name": "Ashen Wyrmling",
        "role": "boss",
        "base_stats": {
            "attack": 22, "defense": 12, "elemental": 24, "speed": 10,
            "max_hp": 260, "max_mana": 999, "crit_rate": 12, "crit_damage": 175, "recharge": 7,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ARTIFACT_SKILLS, "starfall"),
            get_ability_by_id(WEAPON_SKILLS, "frost_lance"),
        ],
        "passive_abilities": [get_ability_by_id(ARMOR_PASSIVES, "iron_skin")],
        "ultimate_ability": get_ability_by_id(ULTIMATE_ABILITIES, "voidstorm"),
    },
]


def get_templates_by_role(role: str) -> list[dict]:
    return [t for t in ENEMY_TEMPLATES if t["role"] == role]


def get_template_by_name(name: str) -> dict:
    for template in ENEMY_TEMPLATES:
        if template["name"] == name:
            return template
    raise KeyError(f"No enemy template named {name!r}")
