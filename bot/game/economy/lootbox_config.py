"""
Seed data for LootboxTemplate rows, plus the rarity table each tier rolls
items from. Same upsert-on-startup pattern as harvesters
(bot/services/lootbox_service.py's ensure_lootbox_templates_seeded).

Each tier's rarity table has a strictly better floor than the one below it
(Common can still roll Common; Rare can't roll below Uncommon; Epic can't
roll below Rare; Legendary can't roll below Epic) so opening a better box
always feels like a step up, not just "same odds, more currency."
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

LOOTBOX_TEMPLATES: list[dict] = [
    {
        "tier": "common",
        "name": "Common Lootbox",
        "description": "A simple satchel of supplies. Everyone's daily bread and butter.",
        "min_gold": 30, "max_gold": 80,
        "min_shards": 0, "max_shards": 0,
        "item_count": 1,
    },
    {
        "tier": "rare",
        "name": "Rare Lootbox",
        "description": "A reinforced chest -- guaranteed at least an Uncommon find.",
        "min_gold": 60, "max_gold": 150,
        "min_shards": 0, "max_shards": 5,
        "item_count": 1,
    },
    {
        "tier": "epic",
        "name": "Epic Lootbox",
        "description": "An ornate coffer humming with power. Guaranteed at least Rare.",
        "min_gold": 150, "max_gold": 300,
        "min_shards": 5, "max_shards": 15,
        "item_count": 2,
    },
    {
        "tier": "legendary",
        "name": "Legendary Lootbox",
        "description": "A relic-bound vault. Guaranteed at least Epic -- the good stuff.",
        "min_gold": 300, "max_gold": 600,
        "min_shards": 15, "max_shards": 40,
        "item_count": 2,
    },
]

LOOTBOX_RARITY_WEIGHTS: dict[str, dict[Rarity, float]] = {
    "common": {
        Rarity.COMMON: 45.0,
        Rarity.UNCOMMON: 30.0,
        Rarity.RARE: 17.0,
        Rarity.EPIC: 6.5,
        Rarity.LEGENDARY: 1.5,
    },
    "rare": {
        Rarity.UNCOMMON: 35.0,
        Rarity.RARE: 38.0,
        Rarity.EPIC: 20.0,
        Rarity.LEGENDARY: 6.0,
        Rarity.MYTHIC: 1.0,
    },
    "epic": {
        Rarity.RARE: 30.0,
        Rarity.EPIC: 40.0,
        Rarity.LEGENDARY: 22.0,
        Rarity.MYTHIC: 6.5,
        Rarity.ANCIENT: 1.5,
    },
    "legendary": {
        Rarity.EPIC: 25.0,
        Rarity.LEGENDARY: 40.0,
        Rarity.MYTHIC: 24.0,
        Rarity.ANCIENT: 9.0,
        Rarity.DIVINE: 2.0,
    },
}

TIER_ORDER = ["common", "rare", "epic", "legendary"]


def tier_for_floor(floor: int) -> str:
    if floor < 3:
        return "common"
    if floor < 6:
        return "rare"
    if floor < 9:
        return "epic"
    return "legendary"
