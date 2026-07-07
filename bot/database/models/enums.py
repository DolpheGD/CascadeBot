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
    WEAPON = "weapon"
    HELMET = "helmet"
    CHEST = "chest"
    LEGGINGS = "leggings"
    BOOTS = "boots"
    RING = "ring"
    NECKLACE = "necklace"
    ARTIFACT = "artifact"


class ItemType(str, enum.Enum):
    EQUIPMENT = "equipment"
    ARTIFACT = "artifact"
    CONSUMABLE = "consumable"
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
