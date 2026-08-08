"""
Seed data + pure helpers for the Cascade HQ base-building layer. Mirrors
harvester_config.py's role: hand-authored, upserted into the DB on startup
(bot/services/base_service.py::ensure_base_catalog_seeded), tunable here
without a migration.

HQ_LEVEL_CONFIG is keyed by the HQ level a player is CURRENTLY at, and
describes what it takes to reach the NEXT level:
  * "building_level_cap" -- the level cap every unlocked building (harvester
    or shrine) is allowed to reach while HQ sits at this level. Upgrading a
    building past this cap requires upgrading the HQ first; a building's own
    `max_level` is a second, independent ceiling (whichever is lower wins).
  * "upgrade_cost" -- a {currency: amount} dict spent (all at once, all
    required) to advance to the next HQ level.

A level with no entry in HQ_LEVEL_CONFIG is the current max HQ level -- there's
nothing further to spend materials on until more levels are authored here.
"""

from __future__ import annotations

HQ_LEVEL_CONFIG: dict[int, dict] = {
    1: {
        "building_level_cap": 3,
        "upgrade_cost": {"gold": 800, "wood": 150, "stone": 150},
    },
    2: {
        "building_level_cap": 6,
        "upgrade_cost": {"gold": 3000, "stone": 400, "metal": 150},
    },
    3: {
        "building_level_cap": 10,
        "upgrade_cost": {"gold": 8000, "metal": 400, "crystal": 100},
    },
    4: {
        "building_level_cap": 14,
        "upgrade_cost": {"gold": 18000, "metal": 700, "crystal": 250},
    },
    # Levels 5-6 exist so the top domain-energy caps and the Legendary /
    # Mythic crates are actually reachable -- an unlock gated behind an
    # HQ level that cannot be reached is dead content.
    5: {
        "building_level_cap": 18,
        "upgrade_cost": {"gold": 40000, "crystal": 600, "xendium": 200},
    },
    6: {
        "building_level_cap": 22,
        "upgrade_cost": {"gold": 90000, "xendium": 500, "permafrost_ore": 350, "void": 100},
    },
    # ------------------------------------------------------------------
    # LEVELS 7-9: the base kept its ceiling while everything else moved.
    #
    # The HQ's building cap reached 22 at level 6, but every shrine and
    # harvester in the game stopped at max_level 10 -- so the cap had been
    # meaningless for the entire back half of the ladder, and the base
    # was fully finished long before the player was. Those templates now
    # go to 20 (see harvester_config / SHRINE_TEMPLATES), and these three
    # levels are what gate the top half of that range.
    #
    # Costs step up hard and lean on the DEEP materials -- Void and
    # Entropy, which only the late regions drop. That is deliberate: the
    # base should be the thing an endgame player is still feeding, and
    # gold alone is farmable enough that a gold-only cost would be a
    # formality rather than a goal.
    # ------------------------------------------------------------------
    7: {
        "building_level_cap": 26,
        "upgrade_cost": {"gold": 180000, "permafrost_ore": 700, "void": 300, "entropy": 100},
    },
    8: {
        "building_level_cap": 30,
        "upgrade_cost": {"gold": 340000, "void": 800, "entropy": 350},
    },
    9: {
        "building_level_cap": 34,
        "upgrade_cost": {"gold": 600000, "void": 1400, "entropy": 800},
    },
}


def building_level_cap(hq_level: int) -> int:
    """The level cap in effect for harvesters/shrines while HQ sits at
    `hq_level`. Past the highest configured level, the last cap holds."""
    if hq_level in HQ_LEVEL_CONFIG:
        return HQ_LEVEL_CONFIG[hq_level]["building_level_cap"]
    highest = max(HQ_LEVEL_CONFIG)
    return HQ_LEVEL_CONFIG[highest]["building_level_cap"]


def upgrade_requirements(hq_level: int) -> dict | None:
    """Cost dict to advance from `hq_level` to `hq_level + 1`, or None if
    `hq_level` is already the max authored HQ level."""
    return HQ_LEVEL_CONFIG.get(hq_level)


def is_max_hq_level(hq_level: int) -> bool:
    return hq_level not in HQ_LEVEL_CONFIG


# ----------------------------------------------------------------------
# Shrines: own-a-copy-and-level-it, like harvesters, but grant a party-wide
# stat bonus instead of producing currency. `stat` must be one of
# bot.game.combat.combatant.STAT_KEYS.
# ----------------------------------------------------------------------

SHRINE_TEMPLATES: list[dict] = [
    {
        "name": "Shrine of Vigor",
        "description": "A warm, pulsing monolith. Bolsters the whole party's vitality.",
        "stat": "max_hp",
        "bonus_type": "flat",
        "base_bonus_per_level": 20.0,
        "max_level": 20,
        "unlock_hq_level": 1,
        "build_cost_gold": 300,
        "base_upgrade_cost": 150,
        "upgrade_cost_growth": 1.32,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Might",
        "description": "Etched with old battle-runes. Sharpens the whole party's strikes.",
        "stat": "attack",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 20,
        "unlock_hq_level": 1,
        "build_cost_gold": 300,
        "base_upgrade_cost": 150,
        "upgrade_cost_growth": 1.32,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Wards",
        "description": "A ring of standing stones that hums faintly. Toughens the party.",
        "stat": "defense",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 20,
        "unlock_hq_level": 2,
        "build_cost_gold": 600,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.35,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Insight",
        "description": "Slowly rotating crystal shards. Amplifies elemental power.",
        "stat": "elemental",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 20,
        "unlock_hq_level": 2,
        "build_cost_gold": 600,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.35,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Haste",
        "description": "Wind never stops moving around this shrine. Quickens the party.",
        "stat": "speed",
        "bonus_type": "flat",
        "base_bonus_per_level": 1.0,
        "max_level": 20,
        "unlock_hq_level": 3,
        "build_cost_gold": 1200,
        "base_upgrade_cost": 500,
        "upgrade_cost_growth": 1.38,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Fortune",
        "description": "Coins never seem to land the same way twice near it. Sharpens crits.",
        "stat": "crit_rate",
        "bonus_type": "flat",
        "base_bonus_per_level": 1.0,
        "max_level": 20,
        "unlock_hq_level": 3,
        "build_cost_gold": 1200,
        "base_upgrade_cost": 500,
        "upgrade_cost_growth": 1.38,
        "upgrade_currency": "gold",
    },
]


# ----------------------------------------------------------------------
# Shop -- REWORKED into a full two-way MATERIALS MARKET.
#
# WHAT CHANGED AND WHY.
#
# 1. Named GEAR listings are gone; lootbox CRATES are back. Selling a
#    specific item ("Runic Robe Bundle", item level 8) competes directly
#    with adventuring for that item, which is the part of the game the
#    loot is meant to pull you back into -- and a player out-levels the
#    shop's gear long before banking the gold for it. A crate is a
#    different purchase: its contents still come from the normal loot
#    tables, so it complements the dungeon rather than replacing it, and
#    it gives late-game gold a sink once every building is maxed. See the
#    LOOTBOX CRATES block further down.
#
# 2. Every material is now both BUYABLE and SELLABLE, from HQ level 1.
#    Previously only wood and stone could be sold and only wood/stone/
#    metal/crystal could be bought, so the six other materials had no
#    gold price at all -- a player sitting on 400 Void had no way to turn
#    it into anything, and a player 20 Entropy short of an upgrade had no
#    way to close the gap. A material with no market isn't a resource,
#    it's clutter.
#
# 3. The low HQ levels are where the DEPTH is now. Levels 1-2 carry the
#    entire 16-listing material market; higher levels add the conversion
#    RECIPES (refining a material into the tier above it), which are the
#    genuinely valuable trades. That inverts the old shape, where the
#    early shop had four listings and everything interesting was gated
#    behind HQ 4-5.
#
# PRICING. Every material has one base gold value derived from its tier
# (see MATERIAL_GOLD_VALUE). Selling pays that value; buying costs it
# multiplied by MARKET_SPREAD. The spread is the whole economy here: it
# means round-tripping a material through the shop LOSES gold, so the
# market can never be farmed as an infinite-gold exploit, and it makes
# "harvest it yourself" always cheaper than "buy it" without needing a
# daily limit to enforce that.
# ----------------------------------------------------------------------

# Gold a single unit of each material SELLS for, by MaterialType.tier
# (see bot/database/models/enums.py). Roughly 3.5x per tier, tracking how
# much rarer each tier is to actually obtain.
MATERIAL_GOLD_VALUE: dict[str, int] = {
    "wood": 3, "stone": 3,
    "metal": 11, "crystal": 11,
    "xendium": 38, "permafrost_ore": 38,
    "void": 130, "entropy": 130,
}

# Buy price = sell price * this. A 2.2x spread is deliberately wide: the
# shop is a convenience, not an arbitrage opportunity, and a player who
# buys what they could have harvested should feel the premium.
MARKET_SPREAD = 2.2

# How many units change hands per transaction, by tier. Bigger blocks for
# cheap materials so trading 400 wood isn't 40 button presses.
MATERIAL_TRADE_BLOCK: dict[str, int] = {
    "wood": 25, "stone": 25,
    "metal": 15, "crystal": 15,
    "xendium": 10, "permafrost_ore": 10,
    "void": 5, "entropy": 5,
}

MATERIAL_LABEL: dict[str, str] = {
    "wood": "Wood", "stone": "Stone", "metal": "Metal", "crystal": "Crystal",
    "xendium": "Xendium", "permafrost_ore": "Permafrost Ore",
    "void": "Void", "entropy": "Entropy",
}

# Which HQ level each material's market opens at. Tiers 0-1 are available
# from the very start (that's the "more options at low levels" goal); the
# rarer two tiers open a little later, purely so a brand-new player isn't
# shown eight listings for materials they've never seen.
MATERIAL_UNLOCK_HQ: dict[str, int] = {
    "wood": 1, "stone": 1, "metal": 1, "crystal": 1,
    "xendium": 2, "permafrost_ore": 2,
    "void": 3, "entropy": 3,
}


def _material_market_listings() -> list[dict]:
    """Generates the buy AND sell listing for every material, rather than
    hand-writing 16 near-identical dicts. Generated because the numbers
    are all derived from one table -- hand-written copies drift the moment
    anyone retunes a price, and a shop whose description disagrees with
    its arithmetic is worse than no shop."""
    listings: list[dict] = []
    for material, value in MATERIAL_GOLD_VALUE.items():
        label = MATERIAL_LABEL[material]
        block = MATERIAL_TRADE_BLOCK[material]
        unlock = MATERIAL_UNLOCK_HQ[material]

        listings.append({
            "name": f"Sell {label}",
            "description": f"The quartermaster buys surplus {label.lower()} at the going rate.",
            "kind": "exchange",
            "unlock_hq_level": unlock,
            "cost_currency": material,
            "cost_amount": block,
            "reward_currency": "gold",
            "reward_amount": value * block,
            "daily_limit": 0,
        })
        listings.append({
            "name": f"Buy {label}",
            "description": f"{label} off the shelf -- pricier than harvesting it, but instant.",
            "kind": "exchange",
            "unlock_hq_level": unlock,
            "cost_currency": "gold",
            "cost_amount": int(value * block * MARKET_SPREAD),
            "reward_currency": material,
            "reward_amount": block,
            "daily_limit": 0,
        })
    return listings

SHOP_LISTINGS: list[dict] = _material_market_listings() + [
    # ------------------------------------------------------------------
    # REROLL TOKEN TRADES.
    #
    # Duplicate character pulls used to be where tokens came from; they
    # now pay Resonance and Echoes instead (resonance_config), which left
    # the substat-reroll economy with no dependable source at all. These
    # two are the dependable one: a gold sink the player controls,
    # daily-limited so it stays a steady trickle rather than a way to
    # convert a fortune into a perfectly-rolled item in one sitting.
    # ------------------------------------------------------------------
    {
        "name": "Attunement Contract",
        "description": "The quartermaster will part with a few reroll tokens for gold.",
        "kind": "exchange",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 900,
        "reward_currency": "reroll_tokens",
        "reward_amount": 6,
        "daily_limit": 4,
    },
    {
        "name": "Bulk Attunement Contract",
        "description": "A standing order for reroll tokens, priced for volume.",
        "kind": "exchange",
        "unlock_hq_level": 4,
        "cost_currency": "crystal",
        "cost_amount": 40,
        "reward_currency": "reroll_tokens",
        "reward_amount": 45,
        "daily_limit": 2,
    },
    # ------------------------------------------------------------------
    # REFINERIES -- convert a material into one of the tier above. These
    # are the shop's actual depth, and the reason to keep levelling HQ:
    # a tier-3 material is worth ~43x a tier-0 one, so the ability to
    # walk cheap surplus up the ladder is worth far more than any flat
    # gold trade. Daily-limited (unlike the plain market listings) so
    # refining stays a steady drip rather than a way to convert an entire
    # wood stockpile into Void in one sitting.
    # ------------------------------------------------------------------
    {
        "name": "Metal Refinery",
        "description": "The quarry's forge can refine stone into metal, slowly.",
        "kind": "exchange",
        "unlock_hq_level": 2,
        "cost_currency": "stone",
        "cost_amount": 60,
        "reward_currency": "metal",
        "reward_amount": 15,
        "daily_limit": 5,
    },
    {
        "name": "Crystal Refinery",
        "description": "A finer forge, pushed further -- refines metal into crystal.",
        "kind": "exchange",
        "unlock_hq_level": 3,
        "cost_currency": "metal",
        "cost_amount": 50,
        "reward_currency": "crystal",
        "reward_amount": 10,
        "daily_limit": 5,
    },
    {
        "name": "Xendium Refinery",
        "description": "Crystal, supercooled and compressed until it destabilises into Xendium.",
        "kind": "exchange",
        "unlock_hq_level": 4,
        "cost_currency": "crystal",
        "cost_amount": 45,
        "reward_currency": "xendium",
        "reward_amount": 10,
        "daily_limit": 4,
    },
    {
        "name": "Permafrost Kiln",
        "description": "Slow-frozen crystal, drawn out into Permafrost Ore.",
        "kind": "exchange",
        "unlock_hq_level": 4,
        "cost_currency": "crystal",
        "cost_amount": 45,
        "reward_currency": "permafrost_ore",
        "reward_amount": 10,
        "daily_limit": 4,
    },
    {
        "name": "Void Condenser",
        "description": "Xendium, collapsed in on itself. The lights dim when it runs.",
        "kind": "exchange",
        "unlock_hq_level": 5,
        "cost_currency": "xendium",
        "cost_amount": 40,
        "reward_currency": "void",
        "reward_amount": 8,
        "daily_limit": 3,
    },
    {
        "name": "Entropy Distillery",
        "description": "Permafrost Ore, unwound down to raw Entropy. Nobody watches this one directly.",
        "kind": "exchange",
        "unlock_hq_level": 5,
        "cost_currency": "permafrost_ore",
        "cost_amount": 40,
        "reward_currency": "entropy",
        "reward_amount": 8,
        "daily_limit": 3,
    },


    # ------------------------------------------------------------------
    # LOOTBOX CRATES. Deliberately back after the gear listings were cut:
    # a crate isn't the same purchase as a specific item. Buying a named
    # weapon competes directly with adventuring for it, which is why that
    # was removed -- a crate is a gamble whose contents still come from
    # the normal loot tables, so it complements the dungeon instead of
    # replacing it, and it gives late-game gold somewhere to go once
    # every building is maxed.
    #
    # Each tier unlocks a level apart and costs steeply more, so crates
    # are the clearest ongoing payoff for pushing HQ higher. Daily limits
    # keep them a steady drip rather than a way to convert a gold pile
    # into an instant armoury.
    # ------------------------------------------------------------------
    {
        "name": "Common Supply Crate",
        "description": "A sealed Cascade supply crate. Contents unknown.",
        "kind": "lootbox",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 450,
        "lootbox_tier": "common",
        "lootbox_quantity": 1,
        "daily_limit": 5,
    },
    {
        "name": "Uncommon Supply Crate",
        "description": "A reinforced crate. Better odds inside.",
        "kind": "lootbox",
        "unlock_hq_level": 2,
        "cost_currency": "gold",
        "cost_amount": 1100,
        "lootbox_tier": "uncommon",
        "lootbox_quantity": 1,
        "daily_limit": 4,
    },
    {
        "name": "Rare Vault Crate",
        "description": "A sealed Cascade vault crate. Only the well-established get one.",
        "kind": "lootbox",
        "unlock_hq_level": 3,
        "cost_currency": "gold",
        "cost_amount": 2600,
        "lootbox_tier": "rare",
        "lootbox_quantity": 1,
        "daily_limit": 3,
    },
    {
        "name": "Epic Coffer",
        "description": "An ornate Cascade coffer, humming faintly.",
        "kind": "lootbox",
        "unlock_hq_level": 4,
        "cost_currency": "gold",
        "cost_amount": 5800,
        "lootbox_tier": "epic",
        "lootbox_quantity": 1,
        "daily_limit": 2,
    },
    {
        "name": "Legendary Reliquary",
        "description": "Requisitioned from the deep vaults. Nobody signs for these twice.",
        "kind": "lootbox",
        "unlock_hq_level": 5,
        "cost_currency": "gold",
        "cost_amount": 12000,
        "lootbox_tier": "legendary",
        "lootbox_quantity": 1,
        "daily_limit": 1,
    },
    {
        "name": "Mythic Cache",
        "description": "The quartermaster pretends not to know where this came from.",
        "kind": "lootbox",
        "unlock_hq_level": 6,
        "cost_currency": "gold",
        "cost_amount": 26000,
        "lootbox_tier": "mythic",
        "lootbox_quantity": 1,
        "daily_limit": 1,
    },
    # ------------------------------------------------------------------
    # SPECIAL -- non-material trades. Kept
    # because Shards are the gacha currency and a gold sink for them is
    # the main thing stopping late-game gold from becoming meaningless
    # once the player owns every harvester and shrine.
    # ------------------------------------------------------------------
    {
        "name": "Shard Trader",
        "description": "A hooded figure who deals only in gold and Cascade Shards.",
        "kind": "exchange",
        "unlock_hq_level": 2,
        "cost_currency": "gold",
        "cost_amount": 1000,
        "reward_currency": "shards",
        "reward_amount": 10,
        "daily_limit": 3,
    },
]
