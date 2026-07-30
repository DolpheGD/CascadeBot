"""
Pure config for the Domains system -- a regenerating energy resource spent
on single-battle "domain challenge" fights against a fixed enemy squad,
for direct on-demand rewards without running a full expedition. See
bot/services/domain_service.py for the energy math and battle handling.

----------------------------------------------------------------------
Energy
----------------------------------------------------------------------
MAX_DOMAIN_ENERGY / ENERGY_REGEN_MINUTES_PER_POINT: a full bar from empty
takes MAX_DOMAIN_ENERGY * ENERGY_REGEN_MINUTES_PER_POINT minutes (120 * 6
= 720 minutes = 12 hours) to regenerate. Player.domain_energy /
domain_energy_updated_at hold the persisted state this accrues against.

----------------------------------------------------------------------
Difficulty tiers
----------------------------------------------------------------------
DOMAIN_DIFFICULTY_TIERS is a SHARED ladder of 6 stages used by every
domain TYPE below -- what differs between, say, the Material Domain and
the Shard Domain at "Hard" difficulty is the REWARD, not the fight, so
the enemy squads are authored once here rather than 6 tiers x 5 types
separately. Deliberately spans the entire roster across all 5 regions and
every role (combat/elite/boss/boss-group/final-boss) -- including combos
that don't occur in a normal expedition (a regular boss paired with an
elite from a different region at "Hard") and set-piece fights normally
gated behind clearing an entire region (the Eruptor Trio boss group at
"Extreme", Xender himself -- the story's final antagonist -- solo at
"Nightmare"). Gated by the player's OWN character level (Player.level,
already-existing state) rather than a separate unlock/completion tracker,
so easier tiers are trivially accessible early and the hardest tier is a
genuine long-term target rather than a hard gate.

Each tier's `squad` is a list of (enemy_name, level) pairs -- enemy_name
must match a bot/game/combat/enemies.py template name exactly;
domain_service builds each via factory.build_enemy_combatant at the
given level, same as a normal dungeon encounter.
"""

from __future__ import annotations

MAX_DOMAIN_ENERGY = 120
ENERGY_REGEN_MINUTES_PER_POINT = 6

DOMAIN_DIFFICULTY_TIERS: list[dict] = [
    {
        "id": "trivial",
        "name": "Trivial",
        "min_player_level": 1,
        "energy_cost": 6,
        "squad": [("Wandering Vagrant", 5)],
    },
    {
        "id": "easy",
        "name": "Easy",
        "min_player_level": 15,
        "energy_cost": 10,
        "squad": [("Corrupted Wastelander", 20), ("Wasteland Rebel", 20)],
    },
    {
        "id": "moderate",
        "name": "Moderate",
        "min_player_level": 30,
        "energy_cost": 16,
        "squad": [("H-Nation Vanguard", 40), ("Xendium Overcharge Drone", 40)],
    },
    {
        # A regular boss paired with an elite from a DIFFERENT region --
        # a combo that would never occur in a normal expedition, since
        # each region draws its boss/elite encounters from its own pool.
        "id": "hard",
        "name": "Hard",
        "min_player_level": 50,
        "energy_cost": 24,
        "squad": [("Corrupted Bli", 55), ("Corrupted Eris Sentry", 55)],
    },
    {
        # The Eruptor Trio -- normally ONLY reachable as Voidcrest
        # Desert's final-boss roll (see enemies.py's BOSS_GROUP_REGION_ROLES).
        # Domains give repeatable access to it without needing to clear a
        # full Voidcrest run each time.
        "id": "extreme",
        "name": "Extreme",
        "min_player_level": 70,
        "energy_cost": 34,
        "squad": [("Borehole", 75), ("Rupture", 75), ("Gatekeeper", 75)],
    },
    {
        # Xender himself, solo -- the story's actual final antagonist
        # (see docs/WORLD_LORE.md), normally a once-per-clear encounter
        # at the very end of an Abyssnia run. The hardest single fight in
        # the game, now available as a repeatable target.
        "id": "nightmare",
        "name": "Nightmare",
        "min_player_level": 90,
        "energy_cost": 50,
        "squad": [("Xender", 95)],
    },
]


def get_tier(tier_id: str) -> dict | None:
    return next((t for t in DOMAIN_DIFFICULTY_TIERS if t["id"] == tier_id), None)


def tier_index(tier_id: str) -> int:
    """Position in the ladder (0 = easiest) -- used for e.g. "3/6" progress
    display. -1 if unknown."""
    for i, t in enumerate(DOMAIN_DIFFICULTY_TIERS):
        if t["id"] == tier_id:
            return i
    return -1


# ----------------------------------------------------------------------
# Domain types -- each grants a different REWARD at each of the 6 shared
# tiers above. `reward_kind` picks how `rewards[tier_id]` is interpreted:
#   - "currency": a {currency: amount} dict, applied via
#     currency_service.add_currency (any key in VALID_CURRENCIES).
#   - "lootbox": a (tier, quantity) tuple, applied via
#     lootbox_service.grant_lootbox.
#   - "xp": a flat int, split across the player's squad via
#     combat_service.apply_character_xp -- same "xp isn't a plain
#     currency" special-case harvester_service.py already uses.
# ----------------------------------------------------------------------

DOMAIN_TYPES: list[dict] = [
    {
        "id": "material",
        "name": "Material Domain",
        "icon": "⛏️",
        "description": "Crafting materials for gear upgrades -- wood and stone early, rarer region materials at higher tiers.",
        "reward_kind": "currency",
        "rewards": {
            "trivial": {"wood": 25, "stone": 25},
            "easy": {"wood": 50, "stone": 50, "metal": 15},
            "moderate": {"metal": 40, "crystal": 25},
            "hard": {"crystal": 60, "xendium": 20, "metal": 30},
            "extreme": {"crystal": 100, "xendium": 40, "permafrost_ore": 30},
            "nightmare": {"crystal": 180, "xendium": 70, "void": 40, "entropy": 40},
        },
    },
    {
        "id": "shard",
        "name": "Shard Domain",
        "icon": "💎",
        "description": "Shards -- the gacha currency.",
        "reward_kind": "currency",
        "rewards": {
            "trivial": {"shards": 10},
            "easy": {"shards": 20},
            "moderate": {"shards": 40},
            "hard": {"shards": 70},
            "extreme": {"shards": 120},
            "nightmare": {"shards": 220},
        },
    },
    {
        "id": "gold",
        "name": "Gold Domain",
        "icon": "🪙",
        "description": "A straightforward pile of gold.",
        "reward_kind": "currency",
        "rewards": {
            "trivial": {"gold": 150},
            "easy": {"gold": 350},
            "moderate": {"gold": 700},
            "hard": {"gold": 1300},
            "extreme": {"gold": 2400},
            "nightmare": {"gold": 4500},
        },
    },
    {
        "id": "lootbox",
        "name": "Lootbox Domain",
        "icon": "🎁",
        "description": "A single lootbox, tier scaling with difficulty.",
        "reward_kind": "lootbox",
        "rewards": {
            "trivial": ("common", 1),
            "easy": ("uncommon", 1),
            "moderate": ("rare", 1),
            "hard": ("epic", 1),
            "extreme": ("legendary", 1),
            "nightmare": ("mythic", 1),
        },
    },
    {
        "id": "xp",
        "name": "XP Domain",
        "icon": "📈",
        "description": "Character XP, split evenly across your whole squad.",
        "reward_kind": "xp",
        "rewards": {
            "trivial": 400,
            "easy": 900,
            "moderate": 1800,
            "hard": 3200,
            "extreme": 5500,
            "nightmare": 9500,
        },
    },
]


def get_domain_type(domain_id: str) -> dict | None:
    return next((d for d in DOMAIN_TYPES if d["id"] == domain_id), None)
