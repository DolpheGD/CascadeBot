"""
The gacha banner: pulls CHARACTERS, spending Shards. Per the Combat
Overhaul spec, this is now the only way to acquire a character -- there is
no other source. Reuses character_service.grant_character() for the actual
grant/dupe-conversion logic so a single pull and a mass pull behave
identically per-roll.

PITY. Player.pity_since_five_star / pity_since_four_star are read and
written by _pull_one on EVERY roll, including each of the ten rolls
inside a 10-pull -- so a multi-pull is exactly ten singles as far as the
guarantees are concerned, and there's no way to game the counters by
choosing one pull shape over the other. See
bot/game/economy/character_gacha_config.py for the tuning and for why
a 5-star also resets the 4-star counter.
"""

from __future__ import annotations

import random

from bot.database.models.character_model import CharacterTemplate
from bot.game.economy.character_gacha_config import (
    FIVE_STAR_HARD_PITY,
    FOUR_STAR_PITY,
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


def _pity_threshold(db, player) -> int:
    """Hard 5-star pity for THIS player: the base threshold minus the
    Research Lab's Expansion branch (gacha_pity_reduction). Floored well
    above zero so research can shorten the guarantee, never remove it."""
    from bot.services import research_service
    reduction = int(research_service.perk_value(db, player.id, "gacha_pity_reduction"))
    return max(20, FIVE_STAR_HARD_PITY - reduction)


def _pull_one(db, player, templates_by_star: dict[int, list[CharacterTemplate]], rng: random.Random) -> dict:
    """One roll. Reads the player's pity counters, rolls against them,
    then updates them from the result BEFORE returning -- so consecutive
    calls within a 10-pull each see the state the previous roll left."""
    hard_pity = _pity_threshold(db, player)
    was_hard_pity = player.pity_since_five_star + 1 >= hard_pity
    was_four_star_pity = (
        not was_hard_pity and player.pity_since_four_star + 1 >= FOUR_STAR_PITY
    )

    star = roll_star_rating(
        rng,
        pulls_since_five_star=player.pity_since_five_star,
        pulls_since_four_star=player.pity_since_four_star,
        hard_pity=hard_pity,
    )

    # Counter updates. A 5-star resets BOTH counters -- it satisfies the
    # 4-star guarantee too, and leaving that one running would hand out a
    # free 4-star immediately after every 5-star.
    if star >= 5:
        player.pity_since_five_star = 0
        player.pity_since_four_star = 0
    elif star == 4:
        player.pity_since_five_star += 1
        player.pity_since_four_star = 0
    else:
        player.pity_since_five_star += 1
        player.pity_since_four_star += 1

    pool = templates_by_star.get(star) or [t for tier in templates_by_star.values() for t in tier]
    template = rng.choice(pool)

    pc, is_new, dupe_reward = character_service.grant_character(db, player, template)
    return {
        "template": template,
        "player_character": pc,
        "is_new": is_new,
        "dupe_reward": dupe_reward,
        # Surfaced so the results embed can call out a guaranteed pull as
        # such -- a pity payout landing with no acknowledgement reads as
        # coincidence, which wastes the reassurance the system exists for.
        "from_pity": (star >= 5 and was_hard_pity) or (star == 4 and was_four_star_pity),
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
