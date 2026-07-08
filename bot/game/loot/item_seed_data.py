"""
Starter item catalog. Without at least one ItemTemplate per slot, gacha,
lootboxes, and combat drops have nothing to roll -- this is what makes the
economy/loot systems actually produce items rather than erroring out with
"no item templates exist yet."

Slots: WEAPON (x2 equippable), HEAD (helmet or necklace, x1), CHEST (x1),
LEGGINGS (x1), BOOTS (x1), ARTIFACT (x2 equippable), SCROLL (x1).

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
    # Head -- helmet or necklace, same slot. Main stat: defense, health,
    # speed, energy (recharge), or mana. May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Iron Helm", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.HEAD,
     "main_stat": "defense", "base_main_stat_value": 8,
     "flavor_text": "Heavy but reliable."},
    {"name": "Leather Cap", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.HEAD,
     "main_stat": "speed", "base_main_stat_value": 6,
     "flavor_text": "Light and unassuming."},
    {"name": "Amulet of Insight", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.HEAD,
     "main_stat": "max_mana", "base_main_stat_value": 18,
     "flavor_text": "Whispers old Cascade secrets to those who listen."},
    {"name": "Pendant of Vigor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.HEAD,
     "main_stat": "max_hp", "base_main_stat_value": 20,
     "flavor_text": "Warm to the touch, even in the coldest depths."},
    {"name": "Charged Circlet", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.HEAD,
     "main_stat": "recharge", "base_main_stat_value": 3,
     "flavor_text": "Faintly crackles with stored Cascade energy."},

    # ---------------------------------------------------------------
    # Chest
    # ---------------------------------------------------------------
    {"name": "Iron Chestplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.CHEST,
     "main_stat": "max_hp", "base_main_stat_value": 40,
     "flavor_text": "Forged to withstand the Cascade's deepest horrors."},
    {"name": "Leather Vest", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.CHEST,
     "main_stat": "speed", "base_main_stat_value": 7,
     "flavor_text": "Favored by scouts who value speed over protection."},
    {"name": "Runic Robe", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.CHEST,
     "main_stat": "max_mana", "base_main_stat_value": 24,
     "flavor_text": "Threaded with sigils that hum when spells are near."},

    # ---------------------------------------------------------------
    # Leggings
    # ---------------------------------------------------------------
    {"name": "Iron Greaves", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.LEGGINGS,
     "main_stat": "defense", "base_main_stat_value": 7,
     "flavor_text": "Sturdy plating for the long descent."},
    {"name": "Leather Leggings", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.LEGGINGS,
     "main_stat": "speed", "base_main_stat_value": 5,
     "flavor_text": "Worn smooth by countless expeditions."},
    {"name": "Battery-Lined Leggings", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.LEGGINGS,
     "main_stat": "recharge", "base_main_stat_value": 3,
     "flavor_text": "Scavenged tech, repurposed for the fight ahead."},

    # ---------------------------------------------------------------
    # Boots
    # ---------------------------------------------------------------
    {"name": "Swift Boots", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.BOOTS,
     "main_stat": "speed", "base_main_stat_value": 8,
     "flavor_text": "Feels lighter than air."},
    {"name": "Iron Boots", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.BOOTS,
     "main_stat": "defense", "base_main_stat_value": 5,
     "flavor_text": "Clunky, but they'll never wear through."},
    {"name": "Wanderer's Treads", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.BOOTS,
     "main_stat": "max_hp", "base_main_stat_value": 15,
     "flavor_text": "Thousands of miles, and still holding together."},

    # ---------------------------------------------------------------
    # Artifacts -- main stat: speed, energy (recharge), attack, elemental,
    # crit damage, or crit rate. May roll an artifact skill.
    # ---------------------------------------------------------------
    {"name": "Band of Fortune", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 6,
     "flavor_text": "Said to guide its wearer toward better fortune."},
    {"name": "Ring of Precision", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_damage", "base_main_stat_value": 15,
     "flavor_text": "Sharpens the wearer's focus in the heat of battle."},
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

    # ---------------------------------------------------------------
    # Scrolls -- always carry exactly one ultimate ability.
    # ---------------------------------------------------------------
    {"name": "Scroll of the Meteor", "item_type": ItemType.SCROLL, "slot": EquipmentSlot.SCROLL,
     "main_stat": "elemental", "base_main_stat_value": 6,
     "flavor_text": "Bound in scorched leather, still warm to the touch."},
    {"name": "Scroll of the Phoenix", "item_type": ItemType.SCROLL, "slot": EquipmentSlot.SCROLL,
     "main_stat": "max_hp", "base_main_stat_value": 10,
     "flavor_text": "Ash never quite settles on its pages."},
    {"name": "Scroll of the Executioner", "item_type": ItemType.SCROLL, "slot": EquipmentSlot.SCROLL,
     "main_stat": "attack", "base_main_stat_value": 6,
     "flavor_text": "The ink was mixed with something best not asked about."},
    {"name": "Scroll of the Void", "item_type": ItemType.SCROLL, "slot": EquipmentSlot.SCROLL,
     "main_stat": "crit_damage", "base_main_stat_value": 8,
     "flavor_text": "Reading it too long makes the room feel farther away."},
]
