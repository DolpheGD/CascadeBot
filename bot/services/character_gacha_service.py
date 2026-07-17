"""
The gacha banner: pulls CHARACTERS, spending Shards. Per the Combat
Overhaul spec, this is now the only way to acquire a character -- there is
no other source. Reuses character_service.grant_character() for the actual
grant/dupe-conversion logic so a single pull and a mass pull behave
identically per-roll.
"""

from __future__ import annotations

import random

from bot.database.models.character_model import CharacterTemplate
from bot.game.economy.character_gacha_config import (
    MULTI_PULL_COST_SHARDS,
    MULTI_PULL_COUNT,
    SINGLE_PULL_COST_SHARDS,
    roll_star_rating,
)
from bot.services import character_service, quest_service
from bot.services.currency_service import spend_currency


def _pullable_templates(db) -> list[CharacterTemplate]:
    """Every character except the free, non-gacha avatar template."""
    return db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()


def _pull_one(db, player, templates_by_star: dict[int, list[CharacterTemplate]], rng: random.Random) -> dict:
    star = roll_star_rating(rng)
    pool = templates_by_star.get(star) or [t for tier in templates_by_star.values() for t in tier]
    template = rng.choice(pool)

    pc, is_new, dupe_reward = character_service.grant_character(db, player, template)
    return {
        "template": template,
        "player_character": pc,
        "is_new": is_new,
        "dupe_reward": dupe_reward,
    }


def _grouped_templates(db) -> dict[int, list[CharacterTemplate]]:
    templates = _pullable_templates(db)
    if not templates:
        raise ValueError("No character templates exist to pull from yet.")
    grouped: dict[int, list[CharacterTemplate]] = {}
    for t in templates:
        grouped.setdefault(t.star_rating, []).append(t)
    return grouped


def pull_single(db, player, rng: random.Random | None = None) -> tuple[bool, str, list[dict]]:
    rng = rng or random.Random()
    if not spend_currency(db, player, "shards", SINGLE_PULL_COST_SHARDS):
        return False, f"Not enough shards (need {SINGLE_PULL_COST_SHARDS}).", []

    grouped = _grouped_templates(db)
    result = _pull_one(db, player, grouped, rng)
    db.commit()
    quest_service.record_progress(db, player, "gacha_pulls")

    tag = "NEW!" if result["is_new"] else "Duplicate"
    return True, f"Pulled {result['template'].name} ({result['template'].star_rating}★) -- {tag}", [result]


def pull_multi(db, player, count: int = MULTI_PULL_COUNT, rng: random.Random | None = None) -> tuple[bool, str, list[dict]]:
    rng = rng or random.Random()
    cost = MULTI_PULL_COST_SHARDS if count == MULTI_PULL_COUNT else SINGLE_PULL_COST_SHARDS * count
    if not spend_currency(db, player, "shards", cost):
        return False, f"Not enough shards (need {cost}).", []

    grouped = _grouped_templates(db)
    results = [_pull_one(db, player, grouped, rng) for _ in range(count)]
    db.commit()
    quest_service.record_progress(db, player, "gacha_pulls", amount=count)

    new_count = sum(1 for r in results if r["is_new"])
    return True, f"Pulled {len(results)} characters ({new_count} new)!", results
