"""
Same upsert-on-startup pattern as harvester/lootbox templates: safe to call
every time the bot starts, keeps existing rows in sync with the seed data,
and never duplicates entries (matched by unique `name`).
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import ItemTemplate
from bot.game.loot.item_seed_data import ITEM_TEMPLATES

# Odds of an ultra-rare template (currently just the "500 Billian Gem
# Giveaway" set) being the one picked, any time pick_random_template() is
# called. Deliberately tiny -- these are meant to be a "did that really
# just drop?!" moment, not a normal part of the loot table.
ULTRA_RARE_CHANCE = 0.002


def ensure_item_templates_seeded(db) -> None:
    for data in ITEM_TEMPLATES:
        existing = db.query(ItemTemplate).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(ItemTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
    db.commit()


def pick_random_template(
    db, rng: random.Random | None = None, rarity=None
) -> ItemTemplate | None:
    """Every random "which item template drops" roll across the bot
    (combat rewards, treasure rooms, lootboxes, gacha, the shop's basic
    item) should go through this instead of `db.query(ItemTemplate).all()`
    + `rng.choice(...)` directly -- it keeps ultra-rare set templates (see
    ItemTemplate.is_ultra_rare) out of the normal pool so they stay
    genuinely rare instead of dropping at the same rate as everything else.

    If `rarity` is given (the target rarity, already decided by the
    caller -- e.g. a gacha/lootbox roll, or a region's rarity cap), only
    templates whose [min_rarity, max_rarity] window actually includes it
    are eligible, so e.g. a Legendary roll can't land on a template that's
    only ever supposed to be Common/Uncommon. Falls back to the
    unfiltered pool if nothing matches (a content gap safety net -- with
    reasonable rarity_range coverage across the catalog this shouldn't
    normally trigger)."""
    rng = rng or random.Random()

    def _matches(t: ItemTemplate) -> bool:
        return rarity is None or t.min_rarity.sort_order <= rarity.sort_order <= t.max_rarity.sort_order

    if rng.random() < ULTRA_RARE_CHANCE:
        ultra = [t for t in db.query(ItemTemplate).filter_by(is_ultra_rare=True).all() if _matches(t)]
        if ultra:
            return rng.choice(ultra)

    normal = [t for t in db.query(ItemTemplate).filter_by(is_ultra_rare=False).all() if _matches(t)]
    if normal:
        return rng.choice(normal)

    # Fall back a step at a time: ignore the rarity filter, then ignore
    # ultra-rare exclusion too, rather than returning nothing.
    normal_any_rarity = db.query(ItemTemplate).filter_by(is_ultra_rare=False).all()
    if normal_any_rarity:
        return rng.choice(normal_any_rarity)

    all_templates = db.query(ItemTemplate).all()
    return rng.choice(all_templates) if all_templates else None
