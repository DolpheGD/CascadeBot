"""
The Forge -- targeted gear acquisition.

WHY IT EXISTS. Every piece of equipment in the game arrives by random
roll: a random template, at a random rarity, with random substats and a
random ability. That's fine as the primary source, but it means a player
who knows exactly what they want -- a Conductor's Coat for their
Amplifier, an Aegis Core for a DEF build -- has no way to work toward it.
The Forge is the deterministic counterweight: you pay materials and you
get the SLOT and RARITY you asked for.

It deliberately does NOT let you pick the exact template or substats.
Choosing the slot and rarity removes the two most painful sources of
randomness; letting you name the item outright would make the loot table
pointless, which is the mistake the old "buy a specific item" shop
listing made.

FOUR OPERATIONS, unlocked across the Forge's levels so it keeps giving
the player something new:

  CRAFT     pick slot + rarity, get an item                (level 1)
  SALVAGE   break an item down into its tier's materials   (level 1)
  REFORGE   re-roll an item's ABILITY, keeping its stats   (level 2)
  TRANSFER  move an ability from one item onto another,
            consuming the donor                            (level 4)

Transfer is the endgame operation and is gated hardest: it's how a player
finally puts the ability they want onto the stat-line they want, which is
the single most valuable thing the Forge can offer.
"""

from __future__ import annotations

from bot.database.models.enums import MaterialType, Rarity

MAX_FORGE_LEVEL = 5

FORGE_UPGRADE_COST: dict[int, dict[str, int]] = {
    1: {"gold": 1000, "wood": 100, "stone": 100},
    2: {"gold": 3800, "stone": 260, "metal": 120},
    3: {"gold": 12000, "metal": 380, "crystal": 140},
    4: {"gold": 36000, "crystal": 450, "xendium": 180},
}

# Forge level -> the highest rarity it can CRAFT. The main upgrade
# incentive, and the reason the Forge stays relevant late: a level-1
# forge makes Commons, a maxed one makes Legendaries.
FORGE_MAX_RARITY: dict[int, Rarity] = {
    1: Rarity.COMMON,
    2: Rarity.UNCOMMON,
    3: Rarity.RARE,
    4: Rarity.EPIC,
    5: Rarity.LEGENDARY,
}

# Which operations each level unlocks.
FORGE_UNLOCKS: dict[str, int] = {
    "craft": 1,
    "salvage": 1,
    "reforge": 2,
    "transfer": 4,
}

# Base material cost to craft, by target rarity. Paid in the materials of
# that rarity's own tier (see MATERIALS_BY_RARITY), so crafting a
# Legendary demands late-game resources rather than a pile of wood.
CRAFT_COST: dict[Rarity, dict[str, int]] = {
    Rarity.COMMON: {"gold": 400, "materials": 20},
    Rarity.UNCOMMON: {"gold": 1200, "materials": 35},
    Rarity.RARE: {"gold": 3500, "materials": 55},
    Rarity.EPIC: {"gold": 9000, "materials": 80},
    Rarity.LEGENDARY: {"gold": 24000, "materials": 120},
}

# Materials a craft/salvage at a given rarity deals in. Three per tier so
# a craft draws on a spread rather than draining one resource, matching
# the same anti-bottleneck rule the gear upgrade bands follow.
MATERIALS_BY_RARITY: dict[Rarity, tuple[MaterialType, ...]] = {
    Rarity.COMMON: (MaterialType.WOOD, MaterialType.STONE),
    Rarity.UNCOMMON: (MaterialType.WOOD, MaterialType.STONE, MaterialType.METAL),
    Rarity.RARE: (MaterialType.STONE, MaterialType.METAL, MaterialType.CRYSTAL),
    Rarity.EPIC: (MaterialType.METAL, MaterialType.CRYSTAL, MaterialType.XENDIUM),
    Rarity.LEGENDARY: (MaterialType.CRYSTAL, MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE),
    Rarity.MYTHIC: (MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE, MaterialType.VOID),
    Rarity.DIVINE: (MaterialType.PERMAFROST_ORE, MaterialType.VOID, MaterialType.ENTROPY),
}

# Salvage returns this fraction of a craft's material cost at the item's
# own rarity. Well under 1.0 on purpose: salvaging is a way to convert
# gear you'll never use into something you will, not a way to launder
# materials in a circle.
SALVAGE_RETURN_PERCENT = 35

# Flat costs for the non-craft operations, scaled by the item's rarity
# tier so working on a Divine item is never cheap.
REFORGE_COST: dict[str, int] = {"gold": 1500, "materials": 25}
TRANSFER_COST: dict[str, int] = {"gold": 6000, "materials": 60}


def forge_upgrade_cost(level: int) -> dict[str, int] | None:
    return FORGE_UPGRADE_COST.get(level)


def is_max_forge_level(level: int) -> bool:
    return level >= MAX_FORGE_LEVEL


def max_craft_rarity(level: int) -> Rarity:
    return FORGE_MAX_RARITY.get(level, FORGE_MAX_RARITY[MAX_FORGE_LEVEL])


def craftable_rarities(level: int) -> list[Rarity]:
    ceiling = max_craft_rarity(level)
    return [r for r in CRAFT_COST if r.sort_order <= ceiling.sort_order]


def operation_unlocked(operation: str, level: int) -> bool:
    return level >= FORGE_UNLOCKS.get(operation, 99)


def materials_for_rarity(rarity: Rarity) -> tuple[MaterialType, ...]:
    return MATERIALS_BY_RARITY[rarity]


def split_materials(total: int, rarity: Rarity) -> dict[str, int]:
    """Spread a material total across that rarity's materials as evenly
    as possible -- the same anti-bottleneck rule the gear upgrade bands
    use, so no single resource gates the Forge either."""
    band = materials_for_rarity(rarity)
    base, extra = divmod(total, len(band))
    out: dict[str, int] = {}
    for i, material in enumerate(band):
        amount = base + (1 if i < extra else 0)
        if amount:
            out[material.value] = amount
    return out
