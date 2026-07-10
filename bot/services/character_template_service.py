"""
Same upsert-on-startup pattern as item/harvester/lootbox templates: safe to
call every time the bot starts, keeps existing rows in sync with the seed
data, and never duplicates entries (matched by unique `name`).
"""

from __future__ import annotations

from bot.database.models.character_model import CharacterTemplate
from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES


def ensure_character_templates_seeded(db) -> None:
    for data in CHARACTER_TEMPLATES:
        existing = db.query(CharacterTemplate).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(CharacterTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
    db.commit()


def get_avatar_template(db) -> CharacterTemplate:
    return db.query(CharacterTemplate).filter_by(is_player_avatar=True).first()
