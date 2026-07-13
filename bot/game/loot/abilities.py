"""
Catalog of abilities gear can roll. Hand-authored (like the naming pools),
not player-specific -- the loot generator picks one at random (filtered by
the item's rolled rarity AND its item_type's pool) and stamps a copy onto
the InventoryItem's active_ability / passive_ability JSON column.

Four separate pools, matching the equipment design:
  * WEAPON_SKILLS   -- active, costs mana. Rolled onto WEAPON items only.
  * ARTIFACT_SKILLS -- active, costs mana. Rolled onto ARTIFACT items only.
  * ULTIMATE_ABILITIES -- kept as a reference catalog for character kit
    design (Combat Overhaul: ultimates now come from each character's kit,
    not gear -- see CharacterTemplate.ultimate_id in character_model.py).
    No longer rolled onto items.
  * ARMOR_PASSIVES  -- passive, always-on or conditional. Rolled onto
    ARMOR/ACCESSORY items only.

`effect` is a small, structured dict rather than free code -- combat reads
`effect["kind"]` and applies matching logic (see bot/game/combat/effects.py).
New effect kinds can be added there without changing the loot generator.

There is no dodge in this game, so no ability here keys off dodging or
grants dodge chance.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

WEAPON_SKILLS: list[dict] = [
    {
        "id": "power_strike",
        "name": "Power Strike",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 15,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 175% ATK damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 175, "damage_stat": "attack"},
    },
    {
        "id": "shield_bash",
        "name": "Shield Bash",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 10,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 90% ATK damage and stun the target for 1 turn.",
        "effect": {"kind": "damage_and_stun", "damage_percent": 90, "damage_stat": "attack", "duration": 1},
    },
    {
        "id": "flame_strike",
        "name": "Flame Strike",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 140% ELE damage and burn the target for 3 turns.",
        "effect": {"kind": "damage_and_dot", "damage_percent": 140, "damage_stat": "elemental",
                   "dot_stat": "elemental", "dot_percent": 10, "duration": 3},
    },
    {
        "id": "frost_lance",
        "name": "Frost Lance",
        "min_rarity": Rarity.RARE,
        "resource_cost": 25,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 120% ELE damage and reduce the target's SPD by 20% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 120, "damage_stat": "elemental",
                   "debuff_stat": "speed", "debuff_percent": -20, "duration": 2},
    },
    {
        "id": "berserker_rage",
        "name": "Berserker's Rage",
        "min_rarity": Rarity.RARE,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Gain 40% ATK for 3 turns, but lose 15% DEF.",
        "effect": {"kind": "self_buff_debuff", "buff_stat": "attack", "buff_percent": 40,
                   "debuff_stat": "defense", "debuff_percent": -15, "duration": 3},
    },
    {
        "id": "rending_cleave",
        "name": "Rending Cleave",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 35,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Strike the target 3 times for 55% ATK damage each.",
        "effect": {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 55, "damage_stat": "attack"},
    },
    {
        "id": "phoenix_dive",
        "name": "Phoenix Dive",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 40,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 200% ATK damage; if this kills the target, restore 25% max HP.",
        "effect": {"kind": "damage_execute_heal", "damage_percent": 200, "damage_stat": "attack",
                   "heal_percent_on_kill": 25},
    },
    {
        "id": "sunder_strike",
        "name": "Sunder Strike",
        "min_rarity": Rarity.RARE,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 130% ATK damage; if the target is below 30% HP, deal 220% ATK damage instead.",
        "effect": {"kind": "execute_below_threshold", "damage_percent": 130,
                   "execute_damage_percent": 220, "damage_stat": "attack",
                   "hp_threshold_percent": 30},
    },
]

ARTIFACT_SKILLS: list[dict] = [
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
        "id": "arcane_burst",
        "name": "Arcane Burst",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 18,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 150% ELE damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 150, "damage_stat": "elemental"},
    },
    {
        "id": "void_grasp",
        "name": "Void Grasp",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 110% ELE damage and reduce the target's DEF by 25% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 110, "damage_stat": "elemental",
                   "debuff_stat": "defense", "debuff_percent": -25, "duration": 2},
    },
    {
        "id": "empowering_ritual",
        "name": "Empowering Ritual",
        "min_rarity": Rarity.RARE,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Gain 35% ELE for 3 turns, but lose 10% DEF.",
        "effect": {"kind": "self_buff_debuff", "buff_stat": "elemental", "buff_percent": 35,
                   "debuff_stat": "defense", "debuff_percent": -10, "duration": 3},
    },
    {
        "id": "soul_siphon",
        "name": "Soul Siphon",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 32,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 130% ELE damage and heal for 40% of your ELE stat.",
        "effect": {"kind": "damage_and_heal_self", "damage_percent": 130, "damage_stat": "elemental",
                   "heal_stat": "elemental", "heal_percent": 40},
    },
    {
        "id": "starfall",
        "name": "Starfall",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 45,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 260% ELE damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 260, "damage_stat": "elemental"},
    },
    {
        "id": "system_purge",
        "name": "System Purge",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal true damage equal to 12% of the target's max HP, ignoring defense.",
        "effect": {"kind": "true_damage_percent_max_hp", "percent": 12},
    },
    {
        "id": "emp_burst",
        "name": "EMP Burst",
        "min_rarity": Rarity.RARE,
        "resource_cost": 24,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 100% ELE damage and drain 20 energy and 15 mana from the target.",
        "effect": {"kind": "damage_and_resource_drain", "damage_percent": 100, "damage_stat": "elemental",
                   "energy_drain": 20, "mana_drain": 15},
    },
    {
        "id": "overclock_repair",
        "name": "Overclock Repair",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Clear all of your own negative effects and restore 25% max HP.",
        "effect": {"kind": "cleanse_self_and_heal", "percent": 25},
    },
    {
        "id": "combat_medic",
        "name": "Combat Medic",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Heal whoever on your side (including you) is lowest on HP% for 30% of their max HP.",
        "effect": {"kind": "heal_lowest_ally_percent_max_hp", "percent": 30},
    },
    {
        "id": "rousing_signal",
        "name": "Rousing Signal",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Grant your whole side 25% ATK for 3 turns.",
        "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 25, "duration": 3},
    },
    {
        "id": "static_field",
        "name": "Static Field",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Reduce the DEF of every enemy by 20% for 2 turns.",
        "effect": {"kind": "team_debuff", "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
    },
    {
        "id": "power_transfer",
        "name": "Power Transfer",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Instantly restore 15 energy and 20 mana to your whole side.",
        "effect": {"kind": "team_resource_restore", "energy_amount": 15, "mana_amount": 20},
    },
    {
        "id": "regenerative_field",
        "name": "Regenerative Field",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 32,
        "resource_type": "mana",
        "cooldown": 5,
        "description": "Your whole side regenerates 8% max HP at the start of each of their turns for 3 turns.",
        "effect": {"kind": "team_regen_over_time", "percent_max_hp_per_turn": 8, "duration": 3},
    },
]

ULTIMATE_ABILITIES: list[dict] = [
    {
        "id": "meteor_ultimate",
        "name": "Meteor",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Unleash a meteor for 320% ELE damage.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 320, "damage_stat": "elemental"},
    },
    {
        "id": "executioners_reckoning",
        "name": "Executioner's Reckoning",
        "min_rarity": Rarity.RARE,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 280% ATK damage; if this kills the target, restore 30% max HP.",
        "effect": {"kind": "damage_execute_heal", "damage_percent": 280, "damage_stat": "attack",
                   "heal_percent_on_kill": 30},
    },
    {
        "id": "phoenix_rebirth",
        "name": "Phoenix Rebirth",
        "min_rarity": Rarity.RARE,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Restore 50% max HP and gain 30% ATK for 3 turns.",
        "effect": {"kind": "heal_and_self_buff", "heal_percent": 50, "buff_stat": "attack",
                   "buff_percent": 30, "duration": 3},
    },
    {
        "id": "cascade_barrage",
        "name": "Cascade Barrage",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Strike the target 4 times for 70% ATK damage each.",
        "effect": {"kind": "multi_hit", "hits": 4, "damage_percent_per_hit": 70, "damage_stat": "attack"},
    },
    {
        "id": "voidstorm",
        "name": "Voidstorm",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 420% ELE damage and reduce the target's DEF by 30% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 420, "damage_stat": "elemental",
                   "debuff_stat": "defense", "debuff_percent": -30, "duration": 2},
    },
    {
        "id": "ascension",
        "name": "Ascension",
        "min_rarity": Rarity.MYTHIC,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 500% ATK damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 500, "damage_stat": "attack"},
    },
    {
        "id": "cataclysm",
        "name": "Cataclysm",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 100,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 150% ELE damage, increased by up to 150% more the lower the target's HP is.",
        "effect": {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 150,
                   "bonus_damage_percent_at_zero_hp": 150, "damage_stat": "elemental"},
    },
]

ARMOR_PASSIVES: list[dict] = [
    {
        "id": "iron_skin",
        "name": "Iron Skin",
        "min_rarity": Rarity.COMMON,
        "trigger": "always",
        "description": "Reduce all incoming damage by 5%.",
        "effect": {"kind": "damage_reduction", "percent": 5},
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
        "id": "vampiric_edge",
        "name": "Vampiric Edge",
        "min_rarity": Rarity.RARE,
        "trigger": "always",
        "description": "Heal for 10% of damage dealt on every hit.",
        "effect": {"kind": "lifesteal", "percent": 10},
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
        "description": "Gain 5% ATK, stacking up to 3 times per fight.",
        "effect": {"kind": "stacking_buff", "buff_stat": "attack", "percent_per_stack": 5,
                   "max_stacks": 3},
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
        "id": "soul_harvest",
        "name": "Soul Harvest",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_kill",
        "description": "Restore 15% max HP and 20 mana when you defeat an enemy.",
        "effect": {"kind": "on_kill_restore", "hp_percent": 15, "mana": 20},
    },
    {
        "id": "arcane_battery",
        "name": "Arcane Battery",
        "min_rarity": Rarity.MYTHIC,
        "trigger": "on_turn_start",
        "description": "Restore 10 mana at the start of every turn.",
        "effect": {"kind": "resource_regen", "resource_type": "mana", "amount": 10},
    },
    {
        "id": "undying_will",
        "name": "Undying Will",
        "min_rarity": Rarity.DIVINE,
        "trigger": "on_low_hp",
        "description": "The first fatal hit in a fight instead leaves you at 1 HP.",
        "effect": {"kind": "prevent_death", "charges_per_combat": 1},
    },
    {
        "id": "retaliation_plating",
        "name": "Retaliation Plating",
        "min_rarity": Rarity.RARE,
        "trigger": "always",
        "description": "20% chance to stun an attacker for 1 turn whenever you take a hit.",
        "effect": {"kind": "chance_stun_attacker", "percent": 20, "duration": 1},
    },
    {
        "id": "support_matrix",
        "name": "Support Matrix",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, restore 5 energy and 8 mana to your whole side.",
        "effect": {"kind": "aura_team_resource_regen", "energy_amount": 5, "mana_amount": 8},
    },
    {
        "id": "regen_field_generator",
        "name": "Regen Field Generator",
        "min_rarity": Rarity.MYTHIC,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, heal your whole side for 4% of their own max HP.",
        "effect": {"kind": "aura_team_regen", "percent": 4},
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
