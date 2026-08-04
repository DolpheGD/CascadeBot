"""
Tuning for co-op guild raids (bot/services/raid_service.py,
bot/database/models/raid_model.py).

Pure config, no imports from the rest of the game, same as every other
*_config module here -- so the numbers below can be retuned without a
migration and without touching any logic.

----------------------------------------------------------------------
How the HP pool is sized
----------------------------------------------------------------------
A raid boss's HP is NOT the enemy template's own HP. It's an independent
pool (GuildRaid.max_hp) sized so that clearing it takes a group rather
than a person: roughly EXPECTED_PARTICIPANTS players spending most of
their MAX_ATTACKS_PER_PLAYER attacks. The battle a player actually
fights uses a normal Combatant built from the template at
`boss_level` -- the shared pool is what their damage is subtracted from,
not what they're punching through in one sitting.

This split is deliberate. If the raid boss were simply an enemy with a
huge HP bar, a single attack could never meaningfully dent it and the
per-attack fight would feel pointless; conversely a boss a strong player
can solo isn't a raid. Separating "the fight you have" from "the pool
you contribute to" lets both be tuned for what they individually need to
feel like.

----------------------------------------------------------------------
Reward tiers
----------------------------------------------------------------------
CONTRIBUTION_TIERS pay out by SHARE OF TOTAL DAMAGE, not by rank. Rank
would mean a server's strongest player always takes the top prize and
everyone else is playing for scraps; share means a newer player who
genuinely showed up and did 10% of the work gets the 10% reward, no
matter who else was in the raid. Everyone who lands a single attack gets
at least the participation tier -- turning up is always worth something.
"""

from __future__ import annotations

import datetime as dt

# How long a raid stays open before expiring unbeaten.
RAID_DURATION = dt.timedelta(days=7)

# Attacks one player may spend on one raid. The scarcity is the whole
# reason a raid is cooperative: nobody can clear the pool alone, so a
# server either coordinates or doesn't finish.
MAX_ATTACKS_PER_PLAYER = 10

# Sizing assumption for the HP pool -- see the module docstring. Tuned
# low on purpose: most Discord servers running a bot like this have a
# handful of active players, not dozens, and a pool sized for 20 people
# is a pool that never gets cleared.
EXPECTED_PARTICIPANTS = 4

# Cooldown between one player's attacks. Stops a single person burning
# all 10 attacks in 30 seconds the moment a raid spawns, which would let
# the fastest clicker monopolise the contribution table before anyone
# else in the server had seen the announcement.
ATTACK_COOLDOWN = dt.timedelta(minutes=10)


RAID_TIERS: list[dict] = [
    {
        "id": "standard",
        "name": "Cascade Incursion",
        "emoji": "🌀",
        # Boss templates are drawn from bot/game/combat/enemies.py by
        # name. Several are listed per tier so consecutive raids in the
        # same server aren't identical.
        "boss_pool": ["Corrupted Bli", "Corrupted Eris Sentry", "H-Nation Vanguard"],
        "boss_level": 45,
        # Pool = this, times EXPECTED_PARTICIPANTS, times
        # MAX_ATTACKS_PER_PLAYER. i.e. "the damage we expect one average
        # attack to do".
        "hp_per_attack": 4_000,
        "min_roster_levels": 0,
        "rewards": {
            # Multiplied by the player's contribution tier below.
            "gold": 4_000,
            "shards": 120,
            "crystal": 60,
            "xendium": 25,
        },
    },
    {
        "id": "elite",
        "name": "Voidcrest Breach",
        "emoji": "🕳️",
        "boss_pool": ["Borehole", "Rupture", "Gatekeeper"],
        "boss_level": 70,
        "hp_per_attack": 11_000,
        "min_roster_levels": 300,
        "rewards": {
            "gold": 11_000,
            "shards": 300,
            "crystal": 140,
            "xendium": 70,
            "void": 30,
        },
    },
    {
        "id": "nightmare",
        "name": "The Xender Protocol",
        "emoji": "☠️",
        "boss_pool": ["Xender"],
        "boss_level": 95,
        "hp_per_attack": 26_000,
        "min_roster_levels": 650,
        "rewards": {
            "gold": 26_000,
            "shards": 700,
            "crystal": 300,
            "xendium": 160,
            "void": 90,
            "entropy": 90,
        },
    },
]


# (minimum share of total damage, multiplier on the tier's reward table,
#  label). Checked highest-first. The top band deliberately pays 2.5x
# rather than 10x: a raid where the top contributor takes almost
# everything teaches everyone else not to bother next time.
CONTRIBUTION_TIERS: list[tuple[float, float, str]] = [
    (0.30, 2.5, "🥇 Vanguard"),
    (0.20, 2.0, "🥈 Spearhead"),
    (0.10, 1.5, "🥉 Striker"),
    (0.05, 1.1, "Contributor"),
    (0.0, 0.75, "Participant"),
]


def get_tier(tier_id: str) -> dict | None:
    return next((t for t in RAID_TIERS if t["id"] == tier_id), None)


def pool_hp_for(tier: dict) -> int:
    """Total shared HP for a raid of this tier -- see the module
    docstring for why this is independent of the boss template's own
    max_hp."""
    return tier["hp_per_attack"] * EXPECTED_PARTICIPANTS * MAX_ATTACKS_PER_PLAYER


def contribution_tier(share: float) -> tuple[float, str]:
    """(reward multiplier, label) for a damage share in 0.0-1.0."""
    for minimum, multiplier, label in CONTRIBUTION_TIERS:
        if share >= minimum:
            return multiplier, label
    return CONTRIBUTION_TIERS[-1][1], CONTRIBUTION_TIERS[-1][2]
