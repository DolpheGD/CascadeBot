"""
Catalog of abilities equipment can roll. These are hand-authored (like the
prefix/suffix pools), not player-specific -- the loot generator picks one at
random (filtered by the item's rolled rarity) and stamps a copy onto the
InventoryItem's active_ability / passive_ability JSON column.

Design decisions this encodes (per project discussion):
  * Active abilities cost a resource (mana/energy) rather than replacing the
    attack action or running on a cooldown -- so `resource_cost` +
    `resource_type` are required, `cooldown` is optional extra friction.
  * Passive abilities can be always-on (`trigger: "always"`) or conditional
    (`trigger: "on_hit"`, `"on_crit"`, `"on_low_hp"`, `"on_kill"`,
    `"on_turn_start"`, `"on_dodge"`). The combat system (built later) is
    expected to fire a hook per trigger type each turn and let any equipped
    item with a matching passive react.

`effect` is a small, structured dict rather than free code -- combat reads
`effect["kind"]` and applies matching logic. New effect kinds can be added
here without changing the loot generator at all.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

ACTIVE_ABILITIES: list[dict] = [
    {
        "id": "flame_strike",
        "name": "Flame Strike",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 150% attack damage and burn the target for 3 turns.",
        "effect": {"kind": "damage_and_dot", "damage_percent": 150, "damage_stat": "magic",
                   "dot_stat": "attack", "dot_percent": 10, "duration": 3},
    },
    {
        "id": "power_strike",
        "name": "Power Strike",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 15,
        "resource_type": "energy",
        "cooldown": 1,
        "description": "Deal 175% attack damage to a single target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 175, "damage_stat": "attack"},
    },
    {
        "id": "frost_lance",
        "name": "Frost Lance",
        "min_rarity": Rarity.RARE,
        "resource_cost": 25,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 120% magic damage and reduce target speed by 20% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 120, "damage_stat": "magic",
                   "debuff_stat": "speed", "debuff_percent": -20, "duration": 2},
    },
    {
        "id": "healing_light",
        "name": "Healing Light",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Restore 30% of max HP.",
        "effect": {"kind": "heal_percent_max_hp", "percent": 30},
    },
    {
        "id": "shield_bash",
        "name": "Shield Bash",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 10,
        "resource_type": "energy",
        "cooldown": 1,
        "description": "Deal 90% attack damage and stun the target for 1 turn.",
        "effect": {"kind": "damage_and_stun", "damage_percent": 90, "damage_stat": "attack", "duration": 1},
    },
    {
        "id": "meteor",
        "name": "Meteor",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 45,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 280% magic damage. Deals 30% less if used two turns in a row.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 280, "damage_stat": "magic"},
    },
    {
        "id": "berserker_rage",
        "name": "Berserker's Rage",
        "min_rarity": Rarity.RARE,
        "resource_cost": 30,
        "resource_type": "energy",
        "cooldown": 3,
        "description": "Gain 40% attack for 3 turns, but lose 15% defense.",
        "effect": {"kind": "self_buff_debuff", "buff_stat": "attack", "buff_percent": 40,
                   "debuff_stat": "defense", "debuff_percent": -15, "duration": 3},
    },
    {
        "id": "phoenix_dive",
        "name": "Phoenix Dive",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 50,
        "resource_type": "mana",
        "cooldown": 5,
        "description": "Deal 200% attack damage; if this kills the target, restore 25% max HP.",
        "effect": {"kind": "damage_execute_heal", "damage_percent": 200, "damage_stat": "attack",
                   "heal_percent_on_kill": 25},
    },
]

PASSIVE_ABILITIES: list[dict] = [
    {
        "id": "vampiric_edge",
        "name": "Vampiric Edge",
        "min_rarity": Rarity.RARE,
        "trigger": "always",
        "description": "Heal for 10% of damage dealt on every hit.",
        "effect": {"kind": "lifesteal", "percent": 10},
    },
    {
        "id": "thornmail",
        "name": "Thornmail",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "always",
        "description": "Reflect 20% of damage taken back to the attacker.",
        "effect": {"kind": "damage_reflect", "percent": 20},
    },
    {
        "id": "second_wind",
        "name": "Second Wind",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_low_hp",
        "description": "The first time HP drops below 25% in a fight, heal 20% of max HP.",
        "effect": {"kind": "heal_percent_max_hp", "percent": 20, "charges_per_combat": 1},
    },
    {
        "id": "executioner",
        "name": "Executioner",
        "min_rarity": Rarity.RARE,
        "trigger": "on_crit",
        "description": "Critical hits deal an additional 15% damage.",
        "effect": {"kind": "crit_damage_bonus", "percent": 15},
    },
    {
        "id": "momentum",
        "name": "Momentum",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "on_turn_start",
        "description": "Gain 5% attack, stacking up to 3 times per fight.",
        "effect": {"kind": "stacking_buff", "buff_stat": "attack", "percent_per_stack": 5,
                   "max_stacks": 3},
    },
    {
        "id": "undying_will",
        "name": "Undying Will",
        "min_rarity": Rarity.ANCIENT,
        "trigger": "on_low_hp",
        "description": "The first fatal hit in a fight instead leaves you at 1 HP.",
        "effect": {"kind": "prevent_death", "charges_per_combat": 1},
    },
    {
        "id": "phantom_step",
        "name": "Phantom Step",
        "min_rarity": Rarity.RARE,
        "trigger": "on_dodge",
        "description": "After dodging, gain 25% dodge chance for 1 turn.",
        "effect": {"kind": "self_buff", "buff_stat": "dodge", "percent": 25, "duration": 1},
    },
    {
        "id": "soul_harvest",
        "name": "Soul Harvest",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_kill",
        "description": "Restore 15% max HP and 20 mana when you defeat an enemy.",
        "effect": {"kind": "on_kill_restore", "hp_percent": 15, "mana": 20},
    },
    {
        "id": "iron_skin",
        "name": "Iron Skin",
        "min_rarity": Rarity.COMMON,
        "trigger": "always",
        "description": "Reduce all incoming damage by 5%.",
        "effect": {"kind": "damage_reduction", "percent": 5},
    },
    {
        "id": "arcane_battery",
        "name": "Arcane Battery",
        "min_rarity": Rarity.MYTHIC,
        "trigger": "on_turn_start",
        "description": "Restore 10 mana at the start of every turn.",
        "effect": {"kind": "resource_regen", "resource_type": "mana", "amount": 10},
    },
]


def abilities_for_rarity(pool: list[dict], rarity: Rarity) -> list[dict]:
    """Every ability in `pool` unlocked at `rarity` or below."""
    return [a for a in pool if a["min_rarity"].sort_order <= rarity.sort_order]


def get_ability_by_id(pool: list[dict], ability_id: str) -> dict:
    """Look up a single ability by id, e.g. for assigning enemy movesets."""
    for ability in pool:
        if ability["id"] == ability_id:
            return ability
    raise KeyError(f"No ability with id {ability_id!r}")
