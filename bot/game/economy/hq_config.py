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
        "max_level": 10,
        "unlock_hq_level": 1,
        "build_cost_gold": 300,
        "base_upgrade_cost": 150,
        "upgrade_cost_growth": 1.5,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Might",
        "description": "Etched with old battle-runes. Sharpens the whole party's strikes.",
        "stat": "attack",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 10,
        "unlock_hq_level": 1,
        "build_cost_gold": 300,
        "base_upgrade_cost": 150,
        "upgrade_cost_growth": 1.5,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Wards",
        "description": "A ring of standing stones that hums faintly. Toughens the party.",
        "stat": "defense",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 10,
        "unlock_hq_level": 2,
        "build_cost_gold": 600,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.55,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Insight",
        "description": "Slowly rotating crystal shards. Amplifies elemental power.",
        "stat": "elemental",
        "bonus_type": "flat",
        "base_bonus_per_level": 3.0,
        "max_level": 10,
        "unlock_hq_level": 2,
        "build_cost_gold": 600,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.55,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Haste",
        "description": "Wind never stops moving around this shrine. Quickens the party.",
        "stat": "speed",
        "bonus_type": "flat",
        "base_bonus_per_level": 1.0,
        "max_level": 10,
        "unlock_hq_level": 3,
        "build_cost_gold": 1200,
        "base_upgrade_cost": 500,
        "upgrade_cost_growth": 1.6,
        "upgrade_currency": "gold",
    },
    {
        "name": "Shrine of Fortune",
        "description": "Coins never seem to land the same way twice near it. Sharpens crits.",
        "stat": "crit_rate",
        "bonus_type": "flat",
        "base_bonus_per_level": 1.0,
        "max_level": 10,
        "unlock_hq_level": 3,
        "build_cost_gold": 1200,
        "base_upgrade_cost": 500,
        "upgrade_cost_growth": 1.6,
        "upgrade_currency": "gold",
    },
]


# ----------------------------------------------------------------------
# Shop: no ownership/leveling, just a purchasable catalog. "exchange"
# listings convert one currency into another (material exchanges);
# "item" listings roll a single low-level InventoryItem from an existing
# ItemTemplate (see bot/game/loot/item_seed_data.py for valid names).
# ----------------------------------------------------------------------

SHOP_LISTINGS: list[dict] = [
    {
        "name": "Sell Wood",
        "description": "The quartermaster always needs lumber.",
        "kind": "exchange",
        "unlock_hq_level": 1,
        "cost_currency": "wood",
        "cost_amount": 20,
        "reward_currency": "gold",
        "reward_amount": 50,
        "daily_limit": 0,
    },
    {
        "name": "Sell Stone",
        "description": "The quartermaster always needs stone.",
        "kind": "exchange",
        "unlock_hq_level": 1,
        "cost_currency": "stone",
        "cost_amount": 20,
        "reward_currency": "gold",
        "reward_amount": 50,
        "daily_limit": 0,
    },
    {
        "name": "Buy Wood",
        "description": "Pricier than harvesting it yourself, but instant.",
        "kind": "exchange",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 70,
        "reward_currency": "wood",
        "reward_amount": 20,
        "daily_limit": 0,
    },
    {
        "name": "Buy Stone",
        "description": "Pricier than harvesting it yourself, but instant.",
        "kind": "exchange",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 70,
        "reward_currency": "stone",
        "reward_amount": 20,
        "daily_limit": 0,
    },
    {
        "name": "Rusty Sword Bundle",
        "description": "A crate of starter weapons. Rolls one basic Iron Sword.",
        "kind": "item",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 150,
        "item_template_name": "Iron Sword",
        "item_level": 1,
        "daily_limit": 3,
    },
    {
        "name": "Traveler's Vest",
        "description": "Basic protection for the road ahead. Rolls one Leather Vest.",
        "kind": "item",
        "unlock_hq_level": 1,
        "cost_currency": "gold",
        "cost_amount": 150,
        "item_template_name": "Leather Vest",
        "item_level": 1,
        "daily_limit": 3,
    },
    {
        "name": "Refine Stone to Metal",
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
