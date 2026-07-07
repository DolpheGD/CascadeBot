"""
Same upsert-on-startup pattern as harvester/lootbox templates: safe to call
every time the bot starts, keeps existing rows in sync with the seed data,
and never duplicates entries (matched by unique `name`).
"""

from __future__ import annotations

from bot.database.models.equipment_model import ItemTemplate
from bot.game.loot.item_seed_data import ITEM_TEMPLATES


def ensure_item_templates_seeded(db) -> None:
    for data in ITEM_TEMPLATES:
        existing = db.query(ItemTemplate).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(ItemTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
    db.commit()
