"""
Seed data for HarvesterTemplate rows. Not authored as Python objects that
live forever in memory -- bot/services/harvester_service.py's
`ensure_harvester_templates_seeded()` upserts these into the DB on startup,
so they can be tuned here and re-synced without a manual migration.
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
        "max_level": 10,
        "max_accumulation_hours": 12.0,
        "base_upgrade_cost": 250,
        "upgrade_cost_growth": 1.6,
    },
]
