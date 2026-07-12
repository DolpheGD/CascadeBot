"""
Each region is a fixed difficulty tier -- picking where to go (the
`region` choice on /adventure) IS the difficulty choice, per the spec:
"Each location could have a different difficulty, with higher difficulty
locations giving more rewards. You should always have to choose where to
go." `level_offset` pushes enemy scaling harder than floor depth alone
would, and `reward_multiplier` scales gold/XP from every source in that
region (see bot/services/combat_service.py and dungeon_service.py).

Progression pacing: `max_item_rarity` and `max_lootbox_tier` STRICTLY cap
what a region can drop -- Glacier 15 (tier 1) can never produce anything
above Rare, full stop, so a new player has to actually work through
Common/Uncommon/Rare gear before the higher regions even have a chance to
hand them something better. Higher-tier regions aren't guaranteed-better
though -- they roll the FULL range up to their cap (a genuine mix of low
and high, still weighted toward common via RARITY_WEIGHTS/
LOOTBOX_RARITY_WEIGHTS), not an exclusively-high-tier firehose.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

REGION_DIFFICULTY: dict[str, dict] = {
    "Glacier 15": {
        "tier": 1, "difficulty_label": "Easy",
        "level_offset": 0, "reward_multiplier": 0.85,
        "max_item_rarity": Rarity.RARE, "max_lootbox_tier": "uncommon",
    },
    "The Wastelands": {
        "tier": 2, "difficulty_label": "Normal",
        "level_offset": 2, "reward_multiplier": 1.05,
        "max_item_rarity": Rarity.EPIC, "max_lootbox_tier": "rare",
    },
    "The Hotlands": {
        "tier": 3, "difficulty_label": "Hard",
        "level_offset": 5, "reward_multiplier": 1.3,
        "max_item_rarity": Rarity.LEGENDARY, "max_lootbox_tier": "epic",
    },
    "Voidcrest Desert": {
        "tier": 4, "difficulty_label": "Nightmare",
        "level_offset": 9, "reward_multiplier": 1.6,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
    },
}

DEFAULT_DIFFICULTY = {
    "tier": 1, "difficulty_label": "Easy", "level_offset": 0, "reward_multiplier": 0.85,
    "max_item_rarity": Rarity.RARE, "max_lootbox_tier": "uncommon",
}


def get_region_difficulty(region: str) -> dict:
    return REGION_DIFFICULTY.get(region, DEFAULT_DIFFICULTY)
