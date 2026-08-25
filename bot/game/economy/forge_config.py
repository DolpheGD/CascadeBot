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

# Upgrade costs come down at the top end with the craft ladder, for the
# same reason. Level 4 -> 5 unlocks Divine crafting and used to cost
# 120,000 gold plus 700 materials that have no passive source -- roughly
# three Divine crafts, paid before making the first one. A gate priced
# well above the thing it gates is a gate nobody opens.
#
# The early levels are unchanged: they were never the problem, and they
# are paid in wood/stone/metal, which harvesters actually produce.
FORGE_UPGRADE_COST: dict[int, dict[str, int]] = {
    1: {"gold": 4000, "stone": 220, "metal": 120},
    2: {"gold": 14000, "metal": 400, "crystal": 160},
    3: {"gold": 30000, "crystal": 380, "xendium": 140},
    4: {"gold": 70000, "xendium": 320, "permafrost_ore": 150},
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
# REPRICED. The old ladder made the Forge pointless at exactly the
# rarities it exists for, and the measurement that shows it is the ratio
# of craft cost to the gold needed to take that same item to MAX LEVEL:
#
#     rarity      craft gold   gold to max   ratio      (old)
#     rare             2,500         3,745   0.67x
#     epic             7,000         7,410   0.94x
#     legendary       18,000        12,700   1.42x
#     mythic          45,000        19,865   2.27x
#     divine         110,000        29,155   3.77x
#
# Crafting a Divine cost nearly FOUR TIMES what it costs to fully upgrade
# one. Acquisition is supposed to be the cheap half of owning an item and
# investment the expensive half; that ladder inverts the relationship,
# and it inverts hardest at the top, where targeting a slot is the only
# reason the Forge exists. A player who does the arithmetic once never
# opens the Forge again, which is what "never worth it" means.
#
# The cause is the curve, not any single number: craft gold multiplied by
# ~2.5x per tier while everything it competes with -- upgrade gold,
# fragment costs, material income -- rises by about 1.5x. Two curves that
# diverge like that are fine near the bottom and absurd at the top.
#
# The new ladder holds the ratio between 0.67x and 1.30x, so a craft
# still costs MORE at higher rarity (rarity should cost more) without
# ever costing multiples of the item's whole future.
#
#     rarity      craft gold   gold to max   ratio      (new)
#     rare             2,500         3,745   0.67x   unchanged
#     epic             6,000         7,410   0.81x
#     legendary       12,000        12,700   0.94x
#     mythic          22,000        19,865   1.11x
#     divine          38,000        29,155   1.30x
#
# MATERIALS COME DOWN HARDER THAN GOLD at the top, because they are the
# real gate. Harvesters produce wood, stone and metal and nothing else --
# crystal, xendium, permafrost ore, void and entropy have NO passive
# income at all and arrive only through deep runs and salvage. A
# 260-material Divine craft priced in three resources a player cannot
# farm passively is a wall wearing a price tag.
CRAFT_COST: dict[Rarity, dict[str, int]] = {
    Rarity.RARE: {"gold": 2500, "materials": 40},
    Rarity.EPIC: {"gold": 6000, "materials": 60},
    Rarity.LEGENDARY: {"gold": 12000, "materials": 90},
    Rarity.MYTHIC: {"gold": 22000, "materials": 130},
    Rarity.DIVINE: {"gold": 38000, "materials": 190},
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
#
# RAISED 35 -> 50 alongside the craft repricing, and it is the same fix
# seen from the other side. High-tier materials have no passive source
# (see the CRAFT_COST note), so the only way to accumulate them is to run
# expeditions and break down what drops. At 35% a player had to salvage
# roughly three unwanted Divines to afford one targeted craft; the pile
# of junk gear that should have been feeding the Forge was instead just
# sitting in the inventory.
#
# 50% still cannot be farmed in a circle -- crafting costs 190 and
# salvaging the result returns 95, so the loop always runs at a loss, and
# the loss is exactly what stops it being an exploit.
SALVAGE_RETURN_PERCENT = 50

# Reforge and Transfer are priced as a FRACTION OF A CRAFT at the same
# rarity, rather than from their own table.
#
# THE ORDERING THAT HAS TO HOLD, at every rarity:
#
#     reforge  <  transfer  <  craft
#
# It follows from what each one gives. Reforge re-rolls one ability on an
# item you keep. Transfer puts a chosen ability on a chosen item but
# DESTROYS the donor -- a real cost that appears in no table, which is
# why it sits below craft rather than above it. Craft produces a whole
# new item and is dearest.
#
# WHY DERIVED AND NOT TABULATED. These used to be flat bases multiplied
# by (rarity.sort_order + 1), which is a LINEAR curve, while the craft
# ladder rises about 1.7x per tier. Two curves with different shapes
# cross, and these did: at the old numbers a Divine transfer cost 42,000
# gold against 38,000 to craft an entire new Divine.
#
# Re-basing the flat numbers fixed Divine and left the ordering inverted
# at rare, epic, legendary and mythic -- transfer cost more than a craft
# at four rarities out of five, and the comment written at the time
# claimed the ordering "now does" hold. It did not. Measuring it printed
# INVERTED on four rows.
#
# A percentage of the craft cost cannot drift, because there is only one
# curve. Change CRAFT_COST and these follow.
REFORGE_PERCENT_OF_CRAFT = 22
TRANSFER_PERCENT_OF_CRAFT = 55

# For rarities the Forge cannot craft (Common, Uncommon) there is no
# craft cost to take a percentage of. They still need a price, because a
# player can reforge a Common. Priced off the salvage baseline instead,
# which is the only other number that describes those rarities.
UNCRAFTABLE_GOLD_PER_MATERIAL = 45


def _craft_basis(rarity: Rarity) -> dict[str, int]:
    """The craft cost Reforge and Transfer are priced against."""
    entry = CRAFT_COST.get(rarity)
    if entry is not None:
        return entry
    materials = SALVAGE_BASE_UNCRAFTABLE.get(rarity, 12)
    return {"gold": materials * UNCRAFTABLE_GOLD_PER_MATERIAL,
            "materials": materials}


def _fraction_of_craft(rarity: Rarity, percent: int) -> dict[str, int]:
    basis = _craft_basis(rarity)
    return {
        "gold": max(1, round(basis["gold"] * percent / 100)),
        "materials": max(1, round(basis["materials"] * percent / 100)),
    }


def reforge_cost(rarity: Rarity) -> dict[str, int]:
    """Gold and materials to re-roll one item's ability."""
    return _fraction_of_craft(rarity, REFORGE_PERCENT_OF_CRAFT)


def transfer_cost(rarity: Rarity) -> dict[str, int]:
    """Gold and materials to move an ability, consuming the donor."""
    return _fraction_of_craft(rarity, TRANSFER_PERCENT_OF_CRAFT)


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
