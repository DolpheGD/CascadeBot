"""
Enemy templates for combat. Deliberately reuse ACTIVE_ABILITIES /
PASSIVE_ABILITIES from bot/game/loot/abilities.py rather than a separate
enemy-ability vocabulary -- an enemy "knowing Flame Strike" and an item
that grants Flame Strike are mechanically identical to the combat engine,
so one effect-resolution system covers both.

This is a small starter roster (one per room type: combat, elite, boss) to
prove the engine end-to-end. Expanding per-region content is a separate,
later content pass.
"""

from __future__ import annotations

from bot.game.loot.abilities import ACTIVE_ABILITIES, PASSIVE_ABILITIES, get_ability_by_id

ENEMY_TEMPLATES: list[dict] = [
    {
        "name": "Goblin",
        "role": "combat",
        "base_stats": {
            "attack": 8, "defense": 4, "magic": 2, "speed": 8, "luck": 3,
            "max_hp": 40, "crit_chance": 5, "crit_damage": 150, "dodge": 5, "healing_bonus": 0,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(ACTIVE_ABILITIES, "shield_bash")],
        "passive_abilities": [],
    },
    {
        "name": "Poison Goblin",
        "role": "combat",
        "base_stats": {
            "attack": 9, "defense": 4, "magic": 6, "speed": 9, "luck": 3,
            "max_hp": 45, "crit_chance": 6, "crit_damage": 150, "dodge": 6, "healing_bonus": 0,
        },
        "level_scale_percent": 8,
        "active_abilities": [get_ability_by_id(ACTIVE_ABILITIES, "flame_strike")],
        "passive_abilities": [],
    },
    {
        "name": "Elite Frenzied Poison Goblin",
        "role": "elite",
        "base_stats": {
            "attack": 16, "defense": 8, "magic": 10, "speed": 11, "luck": 5,
            "max_hp": 110, "crit_chance": 10, "crit_damage": 165, "dodge": 8, "healing_bonus": 0,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ACTIVE_ABILITIES, "flame_strike"),
            get_ability_by_id(ACTIVE_ABILITIES, "berserker_rage"),
        ],
        "passive_abilities": [get_ability_by_id(PASSIVE_ABILITIES, "thornmail")],
    },
    {
        "name": "Ashen Wyrmling",
        "role": "boss",
        "base_stats": {
            "attack": 22, "defense": 12, "magic": 24, "speed": 10, "luck": 6,
            "max_hp": 260, "crit_chance": 12, "crit_damage": 175, "dodge": 6, "healing_bonus": 5,
        },
        "level_scale_percent": 10,
        "active_abilities": [
            get_ability_by_id(ACTIVE_ABILITIES, "meteor"),
            get_ability_by_id(ACTIVE_ABILITIES, "frost_lance"),
        ],
        "passive_abilities": [get_ability_by_id(PASSIVE_ABILITIES, "iron_skin")],
    },
]


def get_templates_by_role(role: str) -> list[dict]:
    return [t for t in ENEMY_TEMPLATES if t["role"] == role]


def get_template_by_name(name: str) -> dict:
    for template in ENEMY_TEMPLATES:
        if template["name"] == name:
            return template
    raise KeyError(f"No enemy template named {name!r}")
