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
    DIVINE = "divine"  # highest rarity -- Ancient tier was removed in the Combat Overhaul

    @property
    def sort_order(self) -> int:
        return list(Rarity).index(self)


class EquipmentSlot(str, enum.Enum):
    """
    Combat Overhaul simplified gear to FOUR slots per character, one item each:
      - WEAPON: grants a weapon skill (active) if the equipped weapon rolled one.
      - ARTIFACT: grants an artifact skill (active) if the equipped artifact
        rolled one. Artifacts may main-stat into HP or DEF now, not just
        offense/utility stats.
      - ARMOR: main defensive piece (defense/hp/speed/recharge/mana), passive-only.
      - ACCESSORY: secondary defensive/utility piece, passive-only.
    Ultimates are no longer tied to gear at all -- they come from the
    character's kit (see character_model.py), so the old SCROLL slot is gone.
    """
    WEAPON = "weapon"
    ARTIFACT = "artifact"
    ARMOR = "armor"
    ACCESSORY = "accessory"


# Every slot holds exactly one item now (no more primary/secondary pairs).
SLOT_CAPACITY: dict[EquipmentSlot, int] = {
    EquipmentSlot.WEAPON: 1,
    EquipmentSlot.ARTIFACT: 1,
    EquipmentSlot.ARMOR: 1,
    EquipmentSlot.ACCESSORY: 1,
}

# Slots that only ever grant passives (weapon/artifact grant actives instead).
ARMOR_SLOTS = {EquipmentSlot.ARMOR, EquipmentSlot.ACCESSORY}

SLOT_DISPLAY_NAME: dict[EquipmentSlot, str] = {
    EquipmentSlot.WEAPON: "Weapon",
    EquipmentSlot.ARTIFACT: "Artifact",
    EquipmentSlot.ARMOR: "Armor",
    EquipmentSlot.ACCESSORY: "Accessory",
}

SLOT_EMOJI: dict[EquipmentSlot, str] = {
    EquipmentSlot.WEAPON: "⚔️",
    EquipmentSlot.ARTIFACT: "🔮",
    EquipmentSlot.ARMOR: "🛡️",
    EquipmentSlot.ACCESSORY: "💍",
}


def slot_index_label(slot: EquipmentSlot, index: int = 0) -> str:
    """Kept for backwards compatibility with older display code -- every
    slot is single-capacity now, so this is always just the slot name."""
    return SLOT_DISPLAY_NAME[slot]


class ItemType(str, enum.Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ARTIFACT = "artifact"
    MATERIAL = "material"
    # SCROLL removed -- ultimates now come from character kits. Any leftover
    # scroll drops should be converted to Substat Catalysts (see
    # bot/game/economy/currency_config.py) via a one-time migration.


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


class CharacterClass(str, enum.Enum):
    """The four roles introduced in the Combat Overhaul. The player's own
    avatar character can freely switch between these (see
    CharacterTemplate.is_player_avatar); pulled characters have a fixed
    class matching their kit design."""
    DPS = "dps"
    SUPPORT_DPS = "support_dps"
    AMPLIFIER = "amplifier"
    SUSTAIN = "sustain"


CLASS_DISPLAY_NAME: dict[CharacterClass, str] = {
    CharacterClass.DPS: "DPS",
    CharacterClass.SUPPORT_DPS: "Support DPS",
    CharacterClass.AMPLIFIER: "Amplifier",
    CharacterClass.SUSTAIN: "Sustain",
}

CLASS_EMOJI: dict[CharacterClass, str] = {
    CharacterClass.DPS: "⚔️",
    CharacterClass.SUPPORT_DPS: "🎯",
    CharacterClass.AMPLIFIER: "📡",
    CharacterClass.SUSTAIN: "💚",
}


class MaterialType(str, enum.Enum):
    """Gear-upgrade materials, tiered by rarity. Earned from harvesters,
    dungeon rewards, and dismantling. Used alongside gold for item
    upgrading (see bot/game/loot/rarity_config.py)."""
    WOOD = "wood"
    STONE = "stone"
    METAL = "metal"
    CRYSTAL = "crystal"
    XENDIUM = "xendium"
    PERMAFROST_ORE = "permafrost_ore"
    VOID = "void"
    ENTROPY = "entropy"

    @property
    def tier(self) -> int:
        """0 = most common, 3 = rarest."""
        return {
            MaterialType.WOOD: 0, MaterialType.STONE: 0,
            MaterialType.METAL: 1, MaterialType.CRYSTAL: 1,
            MaterialType.XENDIUM: 2, MaterialType.PERMAFROST_ORE: 2,
            MaterialType.VOID: 3, MaterialType.ENTROPY: 3,
        }[self]


MATERIAL_DISPLAY_NAME: dict[MaterialType, str] = {
    MaterialType.WOOD: "Wood",
    MaterialType.STONE: "Stone",
    MaterialType.METAL: "Metal",
    MaterialType.CRYSTAL: "Crystal",
    MaterialType.XENDIUM: "Xendium",
    MaterialType.PERMAFROST_ORE: "Permafrost Ore",
    MaterialType.VOID: "Void",
    MaterialType.ENTROPY: "Entropy",
}

MATERIAL_EMOJI: dict[MaterialType, str] = {
    MaterialType.WOOD: "🪵",
    MaterialType.STONE: "🪨",
    MaterialType.METAL: "⚙️",
    MaterialType.CRYSTAL: "💎",
    MaterialType.XENDIUM: "🔷",
    MaterialType.PERMAFROST_ORE: "🧊",
    MaterialType.VOID: "🕳️",
    MaterialType.ENTROPY: "🌀",
}
