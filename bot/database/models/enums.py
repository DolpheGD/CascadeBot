"""
Shared enums used across models and future game systems (loot, combat, dungeon).

Kept as plain str-Enums (not DB enum types) so SQLite stores them as text and
adding new values later never requires a migration.
"""

from __future__ import annotations

import enum


class Rarity(str, enum.Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"
    ANCIENT = "ancient"
    DIVINE = "divine"

    @property
    def sort_order(self) -> int:
        return list(Rarity).index(self)


class EquipmentSlot(str, enum.Enum):
    """
    Nine total gear slots:
      - WEAPON (capacity 2): primary + secondary. Whichever is equipped
        first becomes "primary" (grants weapon skill 1), the second
        becomes "secondary" (weapon skill 2) -- tracked via
        InventoryItem.equip_slot_index.
      - HEAD (capacity 1): a helmet or a necklace -- same slot, cosmetic
        difference only.
      - CHEST / LEGGINGS / BOOTS (capacity 1 each).
      - ARTIFACT (capacity 2): artifact skill 1 + 2, same equip_slot_index
        pattern as WEAPON.
      - SCROLL (capacity 1): determines the player's ultimate ability.
    """
    WEAPON = "weapon"
    HEAD = "head"
    CHEST = "chest"
    LEGGINGS = "leggings"
    BOOTS = "boots"
    ARTIFACT = "artifact"
    SCROLL = "scroll"


# How many of a given slot a player can have equipped at once.
SLOT_CAPACITY: dict[EquipmentSlot, int] = {
    EquipmentSlot.WEAPON: 2,
    EquipmentSlot.HEAD: 1,
    EquipmentSlot.CHEST: 1,
    EquipmentSlot.LEGGINGS: 1,
    EquipmentSlot.BOOTS: 1,
    EquipmentSlot.ARTIFACT: 2,
    EquipmentSlot.SCROLL: 1,
}

# Armor slots specifically -- used to decide "does this slot only grant
# passives" (per design: weapons/artifacts grant active skills, armor only
# grants passives, scrolls always carry the ultimate).
ARMOR_SLOTS = {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGGINGS, EquipmentSlot.BOOTS}

# Display labels, including how to refer to slot index 0 vs 1 for the
# capacity-2 slots (Weapon -> Primary/Secondary, Artifact -> 1/2).
SLOT_DISPLAY_NAME: dict[EquipmentSlot, str] = {
    EquipmentSlot.WEAPON: "Weapon",
    EquipmentSlot.HEAD: "Helmet / Necklace",
    EquipmentSlot.CHEST: "Chestplate",
    EquipmentSlot.LEGGINGS: "Leggings",
    EquipmentSlot.BOOTS: "Boots",
    EquipmentSlot.ARTIFACT: "Artifact",
    EquipmentSlot.SCROLL: "Scroll",
}

SLOT_EMOJI: dict[EquipmentSlot, str] = {
    EquipmentSlot.WEAPON: "⚔️",
    EquipmentSlot.HEAD: "🪖",
    EquipmentSlot.CHEST: "👕",
    EquipmentSlot.LEGGINGS: "👖",
    EquipmentSlot.BOOTS: "👢",
    EquipmentSlot.ARTIFACT: "🔮",
    EquipmentSlot.SCROLL: "📜",
}


def slot_index_label(slot: EquipmentSlot, index: int) -> str:
    """'Primary'/'Secondary' for weapons, '1'/'2' for artifacts, else just the slot name."""
    if slot == EquipmentSlot.WEAPON:
        return "Primary" if index == 0 else "Secondary"
    if slot == EquipmentSlot.ARTIFACT:
        return "1" if index == 0 else "2"
    return SLOT_DISPLAY_NAME[slot]


class ItemType(str, enum.Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ARTIFACT = "artifact"
    SCROLL = "scroll"
    MATERIAL = "material"


class ExpeditionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class RoomType(str, enum.Enum):
    START = "start"
    COMBAT = "combat"
    ELITE = "elite"
    TREASURE = "treasure"
    MERCHANT = "merchant"
    CAMPFIRE = "campfire"
    STORY = "story"
    TRAP = "trap"
    SHRINE = "shrine"
    PUZZLE = "puzzle"
    SECRET = "secret"
    BOSS = "boss"
