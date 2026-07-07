"""
Starter item catalog. Without at least one ItemTemplate per slot, gacha,
lootboxes, and combat drops have nothing to roll -- this is what makes the
economy/loot systems actually produce items rather than erroring out with
"no item templates exist yet."

Seeded on startup the same way harvester/lootbox templates are (see
bot/services/item_template_service.py). Expanding this catalog with more
variety per slot is pure content work -- no code changes needed.
"""

from __future__ import annotations

from bot.database.models.enums import EquipmentSlot, ItemType

ITEM_TEMPLATES: list[dict] = [
    # Weapons
    {"name": "Iron Sword", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 12, "max_sockets": 1,
     "flavor_text": "A well-balanced blade, standard issue for Cascade wanderers."},
    {"name": "Oakwood Bow", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10, "max_sockets": 1,
     "flavor_text": "Carved from ancient oak, still humming faintly with old magic."},
    {"name": "Arcane Staff", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.WEAPON,
     "main_stat": "magic", "base_main_stat_value": 14, "max_sockets": 1,
     "flavor_text": "Channels raw Cascade energy into devastating spells."},

    # Helmets
    {"name": "Iron Helm", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.HELMET,
     "main_stat": "defense", "base_main_stat_value": 8, "max_sockets": 1,
     "flavor_text": "Heavy but reliable."},
    {"name": "Leather Cap", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.HELMET,
     "main_stat": "defense", "base_main_stat_value": 5, "max_sockets": 0,
     "flavor_text": "Light and unassuming."},

    # Chest
    {"name": "Iron Chestplate", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.CHEST,
     "main_stat": "max_hp", "base_main_stat_value": 40, "max_sockets": 2,
     "flavor_text": "Forged to withstand the Cascade's deepest horrors."},
    {"name": "Leather Vest", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.CHEST,
     "main_stat": "max_hp", "base_main_stat_value": 25, "max_sockets": 1,
     "flavor_text": "Favored by scouts who value speed over protection."},

    # Leggings
    {"name": "Iron Greaves", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.LEGGINGS,
     "main_stat": "defense", "base_main_stat_value": 7, "max_sockets": 1,
     "flavor_text": "Sturdy plating for the long descent."},
    {"name": "Leather Leggings", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.LEGGINGS,
     "main_stat": "defense", "base_main_stat_value": 4, "max_sockets": 0,
     "flavor_text": "Worn smooth by countless expeditions."},

    # Boots
    {"name": "Swift Boots", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.BOOTS,
     "main_stat": "speed", "base_main_stat_value": 8, "max_sockets": 1,
     "flavor_text": "Feels lighter than air."},
    {"name": "Iron Boots", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.BOOTS,
     "main_stat": "speed", "base_main_stat_value": 4, "max_sockets": 0,
     "flavor_text": "Clunky, but they'll never wear through."},

    # Rings (two ring slots per player)
    {"name": "Band of Fortune", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.RING,
     "main_stat": "luck", "base_main_stat_value": 6, "max_sockets": 0,
     "flavor_text": "Said to guide its wearer toward better fortune."},
    {"name": "Ring of Precision", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.RING,
     "main_stat": "crit_chance", "base_main_stat_value": 5, "max_sockets": 0,
     "flavor_text": "Sharpens the wearer's focus in the heat of battle."},

    # Necklaces
    {"name": "Amulet of Insight", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.NECKLACE,
     "main_stat": "magic", "base_main_stat_value": 8, "max_sockets": 1,
     "flavor_text": "Whispers old Cascade secrets to those who listen."},
    {"name": "Pendant of Vigor", "item_type": ItemType.EQUIPMENT, "slot": EquipmentSlot.NECKLACE,
     "main_stat": "max_hp", "base_main_stat_value": 20, "max_sockets": 1,
     "flavor_text": "Warm to the touch, even in the coldest depths."},
]
