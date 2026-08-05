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
Difficulty tiers -- UNLOCK (reworked)
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
"Nightmare").

Tiers used to gate on Player.level, which does not work: Player.level is
account-level XP that barely moves (it is NOT the character levels that
decide how strong a squad actually is), so the gate was simultaneously
meaningless and misleading. Every tier now has TWO requirements, both of
which must be met:

  * `required_region` -- a region name that must have been fully CLEARED
    (dungeon_service.has_completed_region -- an Expedition row with
    status COMPLETED, only ever set by beating a run's FINAL boss). None
    means no region requirement. This is the "stage beaten" axis.
  * `min_roster_levels` -- the SUM of every owned PlayerCharacter's level
    across the account. This is the "total character levels" axis, and it
    is what stops "cleared Glacier 15 at character level 7" from opening
    a tier the squad cannot actually handle.

----------------------------------------------------------------------
Difficulty tiers -- SCALING (reworked)
----------------------------------------------------------------------
Enemy levels used to be hardcoded per tier (e.g. Trivial was always a
level-5 Wandering Vagrant). That's why the early tiers were free: a
squad several times stronger than a fixed level-5 enemy walks through it
no matter how the unlock is gated.

Enemy level is now DERIVED from the squad that shows up:

    enemy_level = clamp(avg squad character level + level_offset,
                        min_enemy_level, LEVEL_CAP)

so a domain fight is always posed relative to the party actually
entering it. `level_offset` is the tier's real difficulty knob -- how far
ABOVE (or below) the party each tier punches -- and `min_enemy_level`
keeps a low-level party from trivializing the top tiers by bringing a
weak squad on purpose.

Each tier's `squad` is a list of enemy_name strings -- each must match a
bot/game/combat/enemies.py template name exactly; domain_service builds
each via factory.build_enemy_combatant at the computed level, same as a
normal dungeon encounter.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Energy CAPACITY is an HQ upgrade.
#
# It used to be a flat 120 for everyone from the moment they started,
# which made Cascade HQ irrelevant to the domain system and gave a brand
# new player a bank of energy they had no unlocked tiers to spend it on.
# Capacity now starts small and grows with HQ level, so upgrading the
# base is what lets a player bank more attempts and take longer breaks
# between sessions -- and domains become another reason to invest in HQ
# rather than a parallel system that ignores it.
#
# The REGEN RATE is deliberately untouched by HQ: a bigger bar takes
# proportionally longer to fill, so a higher cap means more stored
# attempts, not faster income. Upgrading buys flexibility, not throughput.
# ----------------------------------------------------------------------
DOMAIN_ENERGY_BY_HQ_LEVEL: dict[int, int] = {
    1: 40,
    2: 60,
    3: 85,
    4: 110,
    5: 140,
}

# Kept as the ceiling any code that can't see an HQ level should assume
# (and the value the bar is drawn against for a maxed base).
MAX_DOMAIN_ENERGY = max(DOMAIN_ENERGY_BY_HQ_LEVEL.values())

ENERGY_REGEN_MINUTES_PER_POINT = 6


def max_domain_energy(hq_level: int) -> int:
    """Energy cap for a player whose Cascade HQ is at `hq_level`. Past the
    highest configured level the last cap holds, same convention as
    hq_config.building_level_cap."""
    if hq_level in DOMAIN_ENERGY_BY_HQ_LEVEL:
        return DOMAIN_ENERGY_BY_HQ_LEVEL[hq_level]
    if hq_level < min(DOMAIN_ENERGY_BY_HQ_LEVEL):
        return DOMAIN_ENERGY_BY_HQ_LEVEL[min(DOMAIN_ENERGY_BY_HQ_LEVEL)]
    return DOMAIN_ENERGY_BY_HQ_LEVEL[max(DOMAIN_ENERGY_BY_HQ_LEVEL)]

# Hard ceiling on a computed enemy level -- mirrors
# character_model.LEVEL_CAP (imported lazily where needed rather than at
# module scope, so this pure-config module keeps importing no DB code).
MAX_ENEMY_LEVEL = 100

DOMAIN_DIFFICULTY_TIERS: list[dict] = [
    {
        "id": "trivial",
        "name": "Trivial",
        "required_region": None,
        "min_roster_levels": 0,
        "energy_cost": 6,
        # Slightly under the party: this tier is the "spend leftover
        # energy without thinking" tier and is meant to be winnable, but
        # -2 rather than the old fixed level 5 means it never becomes a
        # zero-input freebie at high levels either.
        "level_offset": -2,
        "min_enemy_level": 3,
        "squad": ["Wandering Vagrant"],
    },
    {
        "id": "easy",
        "name": "Easy",
        "required_region": "Glacier 15",
        "min_roster_levels": 20,
        "energy_cost": 10,
        "level_offset": 2,
        "min_enemy_level": 10,
        "squad": ["Corrupted Wastelander", "Wasteland Rebel"],
    },
    {
        "id": "moderate",
        "name": "Moderate",
        "required_region": "The Wastelands",
        "min_roster_levels": 55,
        "energy_cost": 16,
        "level_offset": 6,
        "min_enemy_level": 25,
        "squad": ["H-Nation Vanguard", "Xendium Overcharge Drone"],
    },
    {
        # A regular boss paired with an elite from a DIFFERENT region --
        # a combo that would never occur in a normal expedition, since
        # each region draws its boss/elite encounters from its own pool.
        "id": "hard",
        "name": "Hard",
        "required_region": "The Hotlands",
        "min_roster_levels": 110,
        "energy_cost": 24,
        "level_offset": 10,
        "min_enemy_level": 45,
        "squad": ["Corrupted Bli", "Corrupted Eris Sentry"],
    },
    {
        # The Eruptor Trio -- normally ONLY reachable as Voidcrest
        # Desert's final-boss roll (see enemies.py's BOSS_GROUP_REGION_ROLES).
        # Domains give repeatable access to it without needing to clear a
        # full Voidcrest run each time.
        "id": "extreme",
        "name": "Extreme",
        "required_region": "Voidcrest Desert",
        "min_roster_levels": 190,
        "energy_cost": 34,
        "level_offset": 15,
        "min_enemy_level": 65,
        "squad": ["Borehole", "Rupture", "Gatekeeper"],
    },
    {
        # Xender himself, solo -- the story's actual final antagonist
        # (see docs/WORLD_LORE.md), normally a once-per-clear encounter
        # at the very end of an Abyssnia run. The hardest single fight in
        # the game, now available as a repeatable target.
        "id": "nightmare",
        "name": "Nightmare",
        "required_region": "Abyssnia",
        "min_roster_levels": 300,
        "energy_cost": 50,
        "level_offset": 22,
        "min_enemy_level": 85,
        "squad": ["Xender"],
    },
]


def enemy_level_for(tier: dict, avg_squad_level: float) -> int:
    """The level every enemy in `tier` is built at, given the average
    character level of the squad walking in. See the SCALING block in the
    module docstring -- this is what makes a domain fight track the
    party's actual power instead of a hardcoded number."""
    level = round(avg_squad_level + tier.get("level_offset", 0))
    level = max(tier.get("min_enemy_level", 1), level)
    return max(1, min(MAX_ENEMY_LEVEL, level))


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
        "icon": "<:shard:1534383382924890192>",
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
    {
        # Added when duplicate pulls stopped paying reroll tokens (see
        # bot/game/economy/resonance_config.py). That removed the single
        # biggest source in the game overnight, and tokens gate substat
        # rerolling -- the main thing a player does with gear they've
        # already got -- so it needed replacing with something REPEATABLE
        # and on demand rather than another random drop.
        "id": "attunement",
        "name": "Attunement Domain",
        "icon": "🎲",
        "description": "Reroll tokens -- for re-rolling gear substats and adding new ones.",
        "reward_kind": "currency",
        "rewards": {
            "trivial": {"reroll_tokens": 6},
            "easy": {"reroll_tokens": 14},
            "moderate": {"reroll_tokens": 28},
            "hard": {"reroll_tokens": 50},
            "extreme": {"reroll_tokens": 85},
            "nightmare": {"reroll_tokens": 150},
        },
    },
]


def get_domain_type(domain_id: str) -> dict | None:
    return next((d for d in DOMAIN_TYPES if d["id"] == domain_id), None)
