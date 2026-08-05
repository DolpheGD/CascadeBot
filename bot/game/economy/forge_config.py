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

  CRAFT     pick slot + rarity, get an item (Rare and up)  (level 1)
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
    1: {"gold": 4000, "stone": 220, "metal": 120},
    2: {"gold": 14000, "metal": 400, "crystal": 160},
    3: {"gold": 42000, "crystal": 520, "xendium": 200},
    4: {"gold": 120000, "xendium": 480, "permafrost_ore": 220},
}

# Forge level -> the highest rarity it can CRAFT. The main upgrade
# incentive, and the reason the Forge stays relevant late: a level-1
# forge makes Rares, a maxed one makes Divines.
# THE LADDER STARTS AT RARE, not Common.
#
# It used to run Common -> Legendary, which made the first three forge
# levels worthless: Commons and Uncommons drop constantly and for free,
# so paying 400 gold and 20 materials for one was strictly worse than
# walking into any fight. A crafting station whose output you can get
# more cheaply by ignoring it is not a crafting station.
#
# Rare is the floor because that's roughly where the random drop table
# stops handing them out casually (RARITY_WEIGHTS puts Rare at 15%), so
# it's the first tier a player might actually want to TARGET. The top
# end extends to Divine to give the maxed forge somewhere to go.
FORGE_MAX_RARITY: dict[int, Rarity] = {
    1: Rarity.RARE,
    2: Rarity.EPIC,
    3: Rarity.LEGENDARY,
    4: Rarity.MYTHIC,
    5: Rarity.DIVINE,
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
# Common and Uncommon are absent deliberately -- they aren't craftable
# (see FORGE_MAX_RARITY). They remain in MATERIALS_BY_RARITY below,
# because SALVAGE still has to know what to break a Common down into.
CRAFT_COST: dict[Rarity, dict[str, int]] = {
    Rarity.RARE: {"gold": 2500, "materials": 40},
    Rarity.EPIC: {"gold": 7000, "materials": 70},
    Rarity.LEGENDARY: {"gold": 18000, "materials": 110},
    Rarity.MYTHIC: {"gold": 45000, "materials": 170},
    Rarity.DIVINE: {"gold": 110000, "materials": 260},
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

# Material baseline for salvaging a rarity the Forge cannot CRAFT.
#
# Salvage used to price everything off CRAFT_COST, falling back to the
# Common entry. Rebasing the craft ladder at Rare deleted that entry, so
# salvaging a Common -- the most abundant item in the game -- raised a
# KeyError. Uncraftable rarities get their own small values instead of
# borrowing from a table that no longer describes them.
SALVAGE_BASE_UNCRAFTABLE: dict[Rarity, int] = {
    Rarity.COMMON: 12,
    Rarity.UNCOMMON: 22,
}


def salvage_material_base(rarity: Rarity) -> int:
    """Materials a salvage of `rarity` is priced against, whether or not
    the Forge can craft that rarity."""
    entry = CRAFT_COST.get(rarity)
    if entry is not None:
        return entry["materials"]
    return SALVAGE_BASE_UNCRAFTABLE.get(rarity, 12)


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
