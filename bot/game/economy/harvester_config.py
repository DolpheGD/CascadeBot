"""
Seed data for HarvesterTemplate rows. Not authored as Python objects that
live forever in memory -- bot/services/harvester_service.py's
`ensure_harvester_templates_seeded()` upserts these into the DB on startup,
so they can be tuned here and re-synced without a manual migration.

Balancing pass: `level_scaling_exponent` controls how production scales
with level -- 1.0 is linear (level N produces N x base rate), below 1.0 is
sublinear (diminishing returns per level). The Shard Well is deliberately
sublinear: Shards should stay rare relative to gold even at max level,
per the "shard well should scale slower" note, and dailies/harvesters
should feel like the more impactful, reliable income now that dungeon
rewards were trimmed down.
"""

from __future__ import annotations

HARVESTER_TEMPLATES: list[dict] = [
    {
        "name": "Gold Mine",
        "description": "A modest mineshaft at the edge of town. Produces gold over time.",
        "currency": "gold",
        "unlock_cost": 0,  # free starter harvester
        "unlock_currency": "gold",
        "base_rate_per_hour": 10.0,
        "level_scaling_exponent": 1.0,
        "max_level": 20,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 100,
        "upgrade_cost_growth": 1.13,
    },
    {
        # HQ 2, MOVED UP FROM HQ 1.
        #
        # Level-1 HQ offered six harvesters at once -- Gold Mine,
        # Woodcutter's Camp, Stone Quarry, Experience Well, Shard Well
        # and Core Reactor -- which is a shop, not a decision. A new
        # player was reading six listings before they had the gold for
        # two, and the two PREMIUM ones sat at the bottom looking like
        # the obvious goal while being the worst early purchase (both are
        # sublinear, so both pay off slowest).
        #
        # The two premium wells now open at HQ 2, which leaves four
        # basics at HQ 1 -- one free, three cheap, all linear -- and
        # gives the first HQ upgrade something concrete to unlock.
        "name": "Shard Well",
        "description": "A well that slowly draws Cascade Shards up from the depths.",
        "currency": "shards",
        "unlock_cost": 500,
        "unlock_currency": "gold",
        "unlock_hq_level": 2,
        "base_rate_per_hour": 0.5,
        "level_scaling_exponent": 0.75,
        "max_level": 20,
        "max_accumulation_hours": 16.0,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.03,
    },
    {
        # The Card counterpart to the Shard Well. Cards had no passive
        # income at all, so a player who was not voting or running the
        # Core Domain had nothing accruing toward them while offline --
        # which for the game's slowest progression system is exactly
        # backwards.
        #
        # Priced above the Shard Well and slower per hour: a Card is one
        # slot per character and permanent, so its trickle should be the
        # most patient one in the base.
        "name": "Core Reactor",
        "description": "A shielded cell that condenses raw Cascade into Cores. Slowly.",
        "currency": "cores",
        "unlock_cost": 900,
        "unlock_currency": "gold",
        "unlock_hq_level": 2,   # see the Shard Well above
        # SUBLINEAR, like the Shard Well and for the same reason: a
        # premium currency on a linear harvester curve outruns every
        # other source in the game. A first pass used exponent 1.0 and
        # reached 16 card pulls a DAY at max level, against roughly one
        # from the Shard Well -- the passive source would have been the
        # only source worth having.
        "base_rate_per_hour": 0.45,
        "level_scaling_exponent": 0.75,
        "max_level": 20,
        "max_accumulation_hours": 16.0,
        "base_upgrade_cost": 320,
        "upgrade_cost_growth": 1.03,
    },
    {
        "name": "Woodcutter's Camp",
        "description": "A small clearing where lumber is felled and stacked for later use.",
        "currency": "wood",
        "unlock_cost": 0,
        "unlock_currency": "gold",
        "base_rate_per_hour": 6.0,
        "level_scaling_exponent": 1.0,
        "max_level": 20,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 80,
        "upgrade_cost_growth": 1.18,
    },
    {
        "name": "Stone Quarry",
        "description": "A shallow quarry cut into the rock, yielding a steady trickle of stone.",
        "currency": "stone",
        "unlock_cost": 150,
        "unlock_currency": "gold",
        "base_rate_per_hour": 6.0,
        "level_scaling_exponent": 1.0,
        "max_level": 20,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 80,
        "upgrade_cost_growth": 1.18,
    },
    {
        "name": "Metal Forge",
        "description": "A blazing forge, unlocked once Cascade HQ is established. Smelts ore into metal.",
        "currency": "metal",
        "unlock_cost": 800,
        "unlock_currency": "gold",
        "unlock_hq_level": 2,
        "base_rate_per_hour": 4.0,
        "level_scaling_exponent": 0.9,
        "max_level": 20,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 200,
        "upgrade_cost_growth": 1.15,
    },
    {
        # HQ 1, MOVED DOWN FROM HQ 3.
        #
        # Putting it at 3 was the wrong read of what fragments are. The
        # other two gated harvesters produce PREMIUM currencies -- pull
        # fodder, which a new player has no use for and no way to spend
        # well. Fragments are the opposite: they gate levelling gear the
        # player is already wearing, and the very first breakthrough
        # arrives at item level 5, which is reached in the first session.
        #
        # So gating the fragment harvester behind two HQ upgrades meant
        # the earliest wall in the game was backed by the latest source.
        # It unlocks from the start now, alongside the four basics, and
        # the two premium wells at HQ 2 remain what the first HQ upgrade
        # buys.
        #
        # Priced above the other HQ 1 harvesters (1,500 gold against
        # 0-200) so it is a deliberate first goal rather than something
        # bought by accident on day one.
        #
        # Sublinear, like both premium wells, and for the same reason a
        # linear curve was wrong for the Core Reactor: at exponent 1.0
        # and this base rate a maxed Cradle produced ~460/day, which is
        # a Divine item every day and a half from the base alone.
        "name": "Evolution Cradle",
        "description": "A slow bath of raw Cascade. What comes out of it is what lets things change.",
        "currency": "evolution_fragments",
        "unlock_cost": 1500,
        "unlock_currency": "gold",
        "unlock_hq_level": 1,
        "base_rate_per_hour": 0.75,
        "level_scaling_exponent": 0.78,
        "max_level": 20,
        "max_accumulation_hours": 16.0,
        "base_upgrade_cost": 400,
        "upgrade_cost_growth": 1.05,
    },
    {
        "name": "Experience Well",
        "description": "A mystical spring that feeds experience to your champions.",
        "currency": "xp",
        "unlock_cost": 200,
        "unlock_currency": "gold",
        "base_rate_per_hour": 5.0,
        "level_scaling_exponent": 1.0,
        "max_level": 20,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 150,
        "upgrade_cost_growth": 1.07,
    },
]
