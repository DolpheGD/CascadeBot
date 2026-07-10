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
        "max_level": 10,
        "max_accumulation_hours": 8.0,
        "base_upgrade_cost": 100,
        "upgrade_cost_growth": 1.5,
    },
    {
        "name": "Shard Well",
        "description": "A well that slowly draws Cascade Shards up from the depths.",
        "currency": "shards",
        "unlock_cost": 500,
        "unlock_currency": "gold",
        "base_rate_per_hour": 0.5,
        "level_scaling_exponent": 0.75,
        "max_level": 10,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.6,
    },
    {
        "name": "Woodcutter's Camp",
        "description": "A small clearing where lumber is felled and stacked for later use.",
        "currency": "wood",
        "unlock_cost": 0,
        "unlock_currency": "gold",
        "base_rate_per_hour": 6.0,
        "level_scaling_exponent": 1.0,
        "max_level": 10,
        "max_accumulation_hours": 8.0,
        "base_upgrade_cost": 80,
        "upgrade_cost_growth": 1.45,
    },
    {
        "name": "Stone Quarry",
        "description": "A shallow quarry cut into the rock, yielding a steady trickle of stone.",
        "currency": "stone",
        "unlock_cost": 150,
        "unlock_currency": "gold",
        "base_rate_per_hour": 6.0,
        "level_scaling_exponent": 1.0,
        "max_level": 10,
        "max_accumulation_hours": 8.0,
        "base_upgrade_cost": 80,
        "upgrade_cost_growth": 1.45,
    },
]
