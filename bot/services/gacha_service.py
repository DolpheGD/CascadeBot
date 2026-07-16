"""
Pulls a random ItemTemplate from the catalog and rolls it at gacha-boosted
rarity odds (bot/game/economy/gacha_config.py). Reuses the same
LootGenerator as natural drops -- a gacha pull is mechanically "a loot roll
with better odds and a currency cost," not a separate item pipeline.
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import InventoryItem
from bot.game.economy.gacha_config import (
    MULTI_PULL_COST_SHARDS,
    MULTI_PULL_COUNT,
    SINGLE_PULL_COST_SHARDS,
    roll_gacha_rarity,
)
from bot.game.loot.generator import LootGenerator
from bot.services import item_template_service
from bot.services.currency_service import spend_currency


def _pull_one(db, player, item_level: int, rng: random.Random) -> InventoryItem:
    rarity = roll_gacha_rarity(rng)
    template = item_template_service.pick_random_template(db, rng=rng, rarity=rarity)
    if template is None:
        raise ValueError("No item templates exist to pull from yet.")

    generator = LootGenerator(rng=rng)
    item = generator.generate_item(
        template, player_id=player.id, item_level=item_level, rarity_override=rarity
    )
    db.add(item)
    return item


def pull_single(db, player, item_level: int = 1, rng: random.Random | None = None):
    rng = rng or random.Random()
    if not spend_currency(db, player, "shards", SINGLE_PULL_COST_SHARDS):
        return False, f"Not enough shards (need {SINGLE_PULL_COST_SHARDS}).", []

    item = _pull_one(db, player, item_level, rng)
    db.commit()
    db.refresh(item)
    return True, f"Pulled {item.display_name} ({item.rarity.value})!", [item]


def pull_multi(db, player, item_level: int = 1, rng: random.Random | None = None):
    rng = rng or random.Random()
    if not spend_currency(db, player, "shards", MULTI_PULL_COST_SHARDS):
        return False, f"Not enough shards (need {MULTI_PULL_COST_SHARDS}).", []

    items = [_pull_one(db, player, item_level, rng) for _ in range(MULTI_PULL_COUNT)]
    db.commit()
    for item in items:
        db.refresh(item)
    return True, f"Pulled {len(items)} items!", items
