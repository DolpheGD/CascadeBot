"""
Each region is a fixed difficulty tier -- picking where to go (the
`region` choice on /adventure) IS the difficulty choice, per the spec:
"Each location could have a different difficulty, with higher difficulty
locations giving more rewards. You should always have to choose where to
go." `level_offset` pushes enemy scaling harder than floor depth alone
would, and `reward_multiplier` scales gold/XP from every source in that
region (see bot/services/combat_service.py and dungeon_service.py).
"""

from __future__ import annotations

REGION_DIFFICULTY: dict[str, dict] = {
    "Glacier 15": {
        "tier": 1, "difficulty_label": "Easy",
        "level_offset": 0, "reward_multiplier": 1.0,
    },
    "The Wastelands": {
        "tier": 2, "difficulty_label": "Normal",
        "level_offset": 2, "reward_multiplier": 1.15,
    },
    "The Hotlands": {
        "tier": 3, "difficulty_label": "Hard",
        "level_offset": 5, "reward_multiplier": 1.35,
    },
    "Voidcrest Desert": {
        "tier": 4, "difficulty_label": "Nightmare",
        "level_offset": 9, "reward_multiplier": 1.6,
    },
}

DEFAULT_DIFFICULTY = {"tier": 1, "difficulty_label": "Easy", "level_offset": 0, "reward_multiplier": 1.0}


def get_region_difficulty(region: str) -> dict:
    return REGION_DIFFICULTY.get(region, DEFAULT_DIFFICULTY)
