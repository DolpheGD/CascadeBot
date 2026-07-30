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

Combat rework: `level_offset` still drives ELITE/BOSS scaling in a region
(unchanged). `combat_level_offset` is a new, higher offset used ONLY for
normal "combat"-room enemy scaling (see dungeon_service.enter_node) --
normal enemies in the harder regions were badly underscaled relative to
how strong a player actually is by the time they reach those regions, so
they now get pushed harder than elites/bosses do in that same region
rather than just inheriting `level_offset`. `combat_squad_weights` were
also bumped up across every region for a significantly higher average
enemy count per normal fight.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

REGION_DIFFICULTY: dict[str, dict] = {
    "Glacier 15": {
        "tier": 1, "difficulty_label": "Easy",
        "level_offset": 0, "combat_level_offset": 2, "reward_multiplier": 1.3,
        "max_item_rarity": Rarity.EPIC, "max_lootbox_tier": "rare",
        "combat_squad_weights": {1: 30, 2: 40, 3: 25, 4: 5},
        "elite_squad_weights": {1: 100},
    },
    "The Wastelands": {
        "tier": 2, "difficulty_label": "Normal",
        "level_offset": 7, "combat_level_offset": 10, "reward_multiplier": 1.8,
        "max_item_rarity": Rarity.LEGENDARY, "max_lootbox_tier": "epic",
        "combat_squad_weights": {1: 10, 2: 30, 3: 35, 4: 20, 5: 5},
        "elite_squad_weights": {1: 80, 2: 20},
    },
    "The Hotlands": {
        "tier": 3, "difficulty_label": "Hard",
        "level_offset": 15, "combat_level_offset": 20, "reward_multiplier": 2.8,
        "max_item_rarity": Rarity.MYTHIC, "max_lootbox_tier": "legendary",
        "combat_squad_weights": {2: 20, 3: 35, 4: 30, 5: 15},
        "elite_squad_weights": {1: 50, 2: 50},
    },
    "Voidcrest Desert": {
        "tier": 4, "difficulty_label": "Insane",
        "level_offset": 25, "combat_level_offset": 35, "reward_multiplier": 4.5,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "combat_squad_weights": {2: 10, 3: 25, 4: 35, 5: 30},
        "elite_squad_weights": {1: 30, 2: 50, 3: 20},
    },
    "Abyssnia": {
        # The glittering capital of Acatrya itself (see docs/WORLD_LORE.md)
        # -- named in the world doc from the start but never actually
        # built as a playable region until now. The true endgame tier:
        # Rarity.DIVINE and lootbox tier "mythic" are already the hard
        # ceiling of what either system can produce (touching either
        # further would mean a new Rarity value, which needs a DB schema
        # change -- off the table), so this region escalates entirely
        # through harder fights and bigger payouts instead of a higher
        # loot ceiling: a genuine "hardest content in the game" tier
        # rather than a "strictly better loot" tier.
        "tier": 5, "difficulty_label": "Nightmare",
        "level_offset": 35, "combat_level_offset": 48, "reward_multiplier": 6.5,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "combat_squad_weights": {3: 10, 4: 35, 5: 55},
        "elite_squad_weights": {1: 10, 2: 35, 3: 55},
    },
}

DEFAULT_DIFFICULTY = REGION_DIFFICULTY["Glacier 15"]

def get_region_difficulty(region: str) -> dict:
    return REGION_DIFFICULTY.get(region, DEFAULT_DIFFICULTY)


# ----------------------------------------------------------------------
# Region progression gating: regions unlock in `tier` order. The lowest
# tier (Glacier 15) is always available; every other region requires the
# player to have COMPLETED (see ExpeditionStatus.COMPLETED --
# bot/services/dungeon_service.py's resolve_battle_end, set only when the
# FINAL boss of a run is defeated) an expedition in the region immediately
# below it in tier. Derived from REGION_DIFFICULTY's own `tier` values
# rather than a hardcoded chain, so adding a new region here is enough to
# slot it into the unlock order without touching the gating logic itself.
# ----------------------------------------------------------------------

def ordered_regions() -> list[str]:
    """Every region name, sorted easiest (lowest tier) to hardest."""
    return sorted(REGION_DIFFICULTY, key=lambda name: REGION_DIFFICULTY[name]["tier"])


def region_unlock_requirement(region: str) -> str | None:
    """The region that must be COMPLETED before `region` unlocks, or None
    if `region` is the lowest tier (always unlocked)."""
    order = ordered_regions()
    if region not in order or order.index(region) == 0:
        return None
    return order[order.index(region) - 1]