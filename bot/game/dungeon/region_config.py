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

`combat_squad_weights`/`elite_squad_weights` control how many enemies show
up in a single COMBAT/ELITE fight in that region -- easier regions skew
toward smaller fights, harder regions toward bigger ones (see
dungeon_service.enter_node). Which enemy TEMPLATES can even appear in a
region at all (and which boss templates count as "final boss" caliber
there) is a separate axis controlled by each template's own `regions`/
`region_roles` fields in bot/game/combat/enemies.py.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

REGION_DIFFICULTY: dict[str, dict] = {
    "Glacier 15": {
        "tier": 1, "difficulty_label": "Easy",
        "level_offset": 0, "reward_multiplier": 0.85,
        "max_item_rarity": Rarity.RARE, "max_lootbox_tier": "uncommon",
        "combat_squad_weights": {1: 70, 2: 25, 3: 5},
        "elite_squad_weights": {1: 90, 2: 10},
    },
    "The Wastelands": {
        "tier": 2, "difficulty_label": "Normal",
        "level_offset": 2, "reward_multiplier": 1.05,
        "max_item_rarity": Rarity.EPIC, "max_lootbox_tier": "rare",
        "combat_squad_weights": {1: 40, 2: 35, 3: 20, 4: 5},
        "elite_squad_weights": {1: 75, 2: 25},
    },
    "The Hotlands": {
        "tier": 3, "difficulty_label": "Hard",
        "level_offset": 5, "reward_multiplier": 1.3,
        "max_item_rarity": Rarity.LEGENDARY, "max_lootbox_tier": "epic",
        "combat_squad_weights": {1: 25, 2: 30, 3: 30, 4: 15},
        "elite_squad_weights": {1: 55, 2: 45},
    },
    "Voidcrest Desert": {
        "tier": 4, "difficulty_label": "Nightmare",
        "level_offset": 9, "reward_multiplier": 1.6,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "combat_squad_weights": {1: 15, 2: 25, 3: 35, 4: 25},
        "elite_squad_weights": {1: 40, 2: 60},
    },
}

DEFAULT_DIFFICULTY = {
    "tier": 1, "difficulty_label": "Easy", "level_offset": 0, "reward_multiplier": 0.85,
    "max_item_rarity": Rarity.RARE, "max_lootbox_tier": "uncommon",
    "combat_squad_weights": {1: 70, 2: 25, 3: 5},
    "elite_squad_weights": {1: 90, 2: 10},
}


def get_region_difficulty(region: str) -> dict:
    return REGION_DIFFICULTY.get(region, DEFAULT_DIFFICULTY)
