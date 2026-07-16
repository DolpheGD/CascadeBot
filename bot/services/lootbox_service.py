"""
Lootboxes are consumable counters: a player owns some quantity of each
tier, and opening one rolls gold/shards plus item(s) from the existing loot
generator at that tier's boosted rarity odds (bot/game/economy/lootbox_config.py).
Mechanically this is the same pattern as gacha (bot/services/gacha_service.py)
-- a currency-gated loot roll with better-than-natural odds -- just paid for
with an owned box instead of spent shards.
"""

from __future__ import annotations

import random

from bot.database.models.economy_model import LootboxTemplate, PlayerLootbox
from bot.database.models.equipment_model import ItemTemplate
from bot.game.economy.lootbox_config import LOOTBOX_RARITY_WEIGHTS, LOOTBOX_TEMPLATES
from bot.game.loot.generator import LootGenerator
from bot.services.currency_service import add_currency
from bot.services import item_template_service


def ensure_lootbox_templates_seeded(db) -> None:
    """Upserts LOOTBOX_TEMPLATES into the DB. Safe to call every startup."""
    for data in LOOTBOX_TEMPLATES:
        existing = db.query(LootboxTemplate).filter_by(tier=data["tier"]).first()
        if existing is None:
            db.add(LootboxTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
    db.commit()


def get_template(db, tier: str) -> LootboxTemplate | None:
    return db.query(LootboxTemplate).filter_by(tier=tier).first()


def list_player_lootboxes(db, player_id: int) -> list[PlayerLootbox]:
    return (
        db.query(PlayerLootbox)
        .filter_by(player_id=player_id)
        .filter(PlayerLootbox.quantity > 0)
        .all()
    )


def grant_lootbox(db, player, tier: str, quantity: int = 1) -> None:
    template = get_template(db, tier)
    if template is None:
        raise ValueError(f"No lootbox template for tier {tier!r}")

    owned = (
        db.query(PlayerLootbox)
        .filter_by(player_id=player.id, template_id=template.id)
        .first()
    )
    if owned is None:
        owned = PlayerLootbox(player_id=player.id, template_id=template.id, quantity=0)
        db.add(owned)

    owned.quantity += quantity
    db.commit()


def _roll_rarity(tier: str, rng: random.Random):
    weights = LOOTBOX_RARITY_WEIGHTS[tier]
    rarities = list(weights.keys())
    return rng.choices(rarities, weights=list(weights.values()), k=1)[0]


def open_lootboxes(
    db, player, tier: str, count: int = 1, item_level: int = 1, rng: random.Random | None = None
) -> tuple[bool, str, dict]:
    """Opens `count` boxes of `tier` at once. Returns (ok, message, rewards)
    where rewards = {"gold": int, "shards": int, "items": [InventoryItem]}."""
    rng = rng or random.Random()

    template = get_template(db, tier)
    if template is None:
        return False, f"No such lootbox tier: {tier}", {}

    owned = (
        db.query(PlayerLootbox)
        .filter_by(player_id=player.id, template_id=template.id)
        .first()
    )
    if owned is None or owned.quantity < count:
        have = owned.quantity if owned else 0
        return False, f"You only have {have} {template.name}(s).", {}

    total_gold = 0
    total_shards = 0
    items = []
    generator = LootGenerator(rng=rng)

    for _ in range(count):
        total_gold += rng.randint(template.min_gold, template.max_gold)
        if template.max_shards > 0:
            total_shards += rng.randint(template.min_shards, template.max_shards)

        for _ in range(template.item_count):
            rarity = _roll_rarity(tier, rng)
            item_template = item_template_service.pick_random_template(db, rng=rng, rarity=rarity)
            if item_template is None:
                continue
            item = generator.generate_item(
                item_template, player_id=player.id, item_level=item_level, rarity_override=rarity
            )
            db.add(item)
            items.append(item)

    owned.quantity -= count
    db.commit()

    if total_gold:
        add_currency(db, player, "gold", total_gold)
    if total_shards:
        add_currency(db, player, "shards", total_shards)

    for item in items:
        db.refresh(item)

    rewards = {"gold": total_gold, "shards": total_shards, "items": items}
    return True, f"Opened {count} {template.name}(s)!", rewards
