"""
Seed data for LootboxTemplate rows, plus the rarity table each tier rolls
items from. Same upsert-on-startup pattern as harvesters
(bot/services/lootbox_service.py's ensure_lootbox_templates_seeded).

Each tier's rarity table has a strictly better floor than the one below it
so opening a better box always feels like a step up, not just "same odds,
more currency."

Economy pass (per the balancing spec): more lootbox TIERS exist now (six,
up from four) so players have more boxes dropping/rewarded overall, but the
top end (Mythic/Divine gear, and the boxes that can roll them) is pushed
further out of reach than before -- Divine essentially never drops outside
the top-tier box, and even there it's a sliver of a chance.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

LOOTBOX_TEMPLATES: list[dict] = [
    {
        "tier": "common",
        "name": "Common Lootbox",
        "description": "A simple satchel of supplies. Everyone's daily bread and butter.",
        "min_gold": 20, "max_gold": 55,
        "min_shards": 0, "max_shards": 0,
        "item_count": 1,
    },
    {
        "tier": "uncommon",
        "name": "Uncommon Lootbox",
        "description": "A sturdy sack -- a small step up from the basics.",
        "min_gold": 35, "max_gold": 90,
        "min_shards": 0, "max_shards": 2,
        "item_count": 1,
    },
    {
        "tier": "rare",
        "name": "Rare Lootbox",
        "description": "A reinforced chest -- guaranteed at least an Uncommon find.",
        "min_gold": 50, "max_gold": 130,
        "min_shards": 0, "max_shards": 5,
        "item_count": 1,
    },
    {
        "tier": "epic",
        "name": "Epic Lootbox",
        "description": "An ornate coffer humming with power. Guaranteed at least Rare.",
        "min_gold": 100, "max_gold": 220,
        "min_shards": 4, "max_shards": 12,
        "item_count": 2,
    },
    {
        "tier": "legendary",
        "name": "Legendary Lootbox",
        "description": "A relic-bound vault. Guaranteed at least Epic -- the good stuff.",
        "min_gold": 220, "max_gold": 450,
        "min_shards": 10, "max_shards": 28,
        "item_count": 2,
    },
    {
        "tier": "mythic",
        "name": "Mythic Lootbox",
        "description": "A pulsing, reality-thin container. Rare to find, rarer to open on nothing.",
        "min_gold": 400, "max_gold": 800,
        "min_shards": 25, "max_shards": 60,
        "item_count": 2,
    },
]

LOOTBOX_RARITY_WEIGHTS: dict[str, dict[Rarity, float]] = {
    "common": {
        Rarity.COMMON: 55.0,
        Rarity.UNCOMMON: 32.0,
        Rarity.RARE: 11.0,
        Rarity.EPIC: 2.0,
    },
    "uncommon": {
        Rarity.COMMON: 25.0,
        Rarity.UNCOMMON: 42.0,
        Rarity.RARE: 25.0,
        Rarity.EPIC: 7.0,
        Rarity.LEGENDARY: 1.0,
    },
    "rare": {
        Rarity.UNCOMMON: 30.0,
        Rarity.RARE: 42.0,
        Rarity.EPIC: 22.0,
        Rarity.LEGENDARY: 5.5,
        Rarity.MYTHIC: 0.5,
    },
    "epic": {
        Rarity.RARE: 32.0,
        Rarity.EPIC: 42.0,
        Rarity.LEGENDARY: 21.0,
        Rarity.MYTHIC: 4.5,
        Rarity.DIVINE: 0.5,
    },
    "legendary": {
        Rarity.EPIC: 28.0,
        Rarity.LEGENDARY: 42.0,
        Rarity.MYTHIC: 26.0,
        Rarity.DIVINE: 4.0,
    },
    "mythic": {
        Rarity.LEGENDARY: 30.0,
        Rarity.MYTHIC: 55.0,
        Rarity.DIVINE: 15.0,
    },
}

TIER_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def tier_for_floor(floor: int) -> str:
    if floor < 7:
        return "common"
    if floor < 14:
        return "uncommon"
    if floor < 21:
        return "rare"
    if floor < 28:
        return "epic"
    if floor < 35:
        return "legendary"
    return "mythic"


def tier_for_floor_and_region(floor: int, max_lootbox_tier: str) -> str:
    """Combines floor-depth progression with the region's strict cap (see
    bot/game/dungeon/region_config.py) -- whichever is LOWER wins, so an
    easy region can never produce a better box just because the player
    pushed deep into a long run there."""
    floor_tier = tier_for_floor(floor)
    floor_index = TIER_ORDER.index(floor_tier)
    cap_index = TIER_ORDER.index(max_lootbox_tier) if max_lootbox_tier in TIER_ORDER else len(TIER_ORDER) - 1
    return TIER_ORDER[min(floor_index, cap_index)]
