"""
Starter item catalog. Without at least one ItemTemplate per slot, gacha,
lootboxes, and combat drops have nothing to roll -- this is what makes the
economy/loot systems actually produce items rather than erroring out with
"no item templates exist yet."

Combat Overhaul slots (one item each, per character): WEAPON, ARTIFACT,
ARMOR, ACCESSORY. The old HEAD/CHEST/LEGGINGS/BOOTS split has been merged
into a single ARMOR slot, and SCROLL is gone entirely (ultimates now come
from character kits -- see bot/game/characters/character_seed_data.py).

Seeded on startup the same way harvester/lootbox templates are (see
bot/services/item_template_service.py). Expanding this catalog with more
variety per slot is pure content work -- no code changes needed.
"""

from __future__ import annotations

from bot.database.models.enums import EquipmentSlot, ItemType

ITEM_TEMPLATES: list[dict] = [
    # ---------------------------------------------------------------
    # Weapons -- main stat is attack or elemental. May roll a weapon skill.
    # ---------------------------------------------------------------
    {"name": "Iron Sword", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 12,
     "flavor_text": "A well-balanced blade, standard issue for Cascade wanderers."},
    {"name": "Oakwood Bow", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "flavor_text": "Carved from ancient oak, still humming faintly with old magic."},
    {"name": "Twin Daggers", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 9,
     "flavor_text": "Fast, light, and favored by scouts who strike before being seen."},
    {"name": "Arcane Staff", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 14,
     "flavor_text": "Channels raw Cascade energy into devastating spells."},
    {"name": "Voidglass Wand", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 13,
     "flavor_text": "Forged from crystallized Void matter -- cold to hold, colder to face."},

    # ---------------------------------------------------------------
    # Armor -- single slot now. Main stat: defense, health, speed, energy
    # (recharge), or mana. May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Iron Chestplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 14,
     "flavor_text": "Forged to withstand the Cascade's deepest horrors."},
    {"name": "Leather Vest", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "speed", "base_main_stat_value": 8,
     "flavor_text": "Favored by scouts who value speed over protection."},
    {"name": "Runic Robe", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_mana", "base_main_stat_value": 24,
     "flavor_text": "Threaded with sigils that hum when spells are near."},
    {"name": "Pendant of Vigor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_hp", "base_main_stat_value": 40,
     "flavor_text": "Warm to the touch, even in the coldest depths."},
    {"name": "Charged Plating", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Faintly crackles with stored Cascade energy."},

    # ---------------------------------------------------------------
    # Accessories -- secondary defensive/utility slot. Main stat: defense,
    # health, speed, energy (recharge), mana, crit rate, or crit damage.
    # May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Amulet of Insight", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_mana", "base_main_stat_value": 18,
     "flavor_text": "Whispers old Cascade secrets to those who listen."},
    {"name": "Swift Boots", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "speed", "base_main_stat_value": 9,
     "flavor_text": "Feels lighter than air."},
    {"name": "Iron Greaves", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "defense", "base_main_stat_value": 8,
     "flavor_text": "Sturdy plating for the long descent."},
    {"name": "Battery-Lined Bracer", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Scavenged tech, repurposed for the fight ahead."},
    {"name": "Ring of Precision", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 15,
     "flavor_text": "Sharpens the wearer's focus in the heat of battle."},
    {"name": "Wanderer's Treads", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_hp", "base_main_stat_value": 25,
     "flavor_text": "Thousands of miles, and still holding together."},

    # ---------------------------------------------------------------
    # Artifacts -- main stat: speed, energy (recharge), attack, elemental,
    # crit damage, crit rate, HP, or DEF. May roll an artifact skill.
    # ---------------------------------------------------------------
    {"name": "Band of Fortune", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 6,
     "flavor_text": "Said to guide its wearer toward better fortune."},
    {"name": "Cascade Core Shard", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 10,
     "flavor_text": "A fragment of the Cascade itself, still faintly pulsing."},
    {"name": "Kinetic Battery", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Stores momentum and releases it as raw energy."},
    {"name": "Wanderer's Compass", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "speed", "base_main_stat_value": 7,
     "flavor_text": "Always points toward the fastest way forward."},
    {"name": "Bloodfang Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "attack", "base_main_stat_value": 11,
     "flavor_text": "Carved from a predator's tooth, still hungry."},
    {"name": "Bulwark Idol", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "defense", "base_main_stat_value": 12,
     "flavor_text": "An old ward-stone, radiating quiet stubbornness."},
    {"name": "Heartroot Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 35,
     "flavor_text": "Grown, not forged -- it beats faintly, like something alive."},
]
