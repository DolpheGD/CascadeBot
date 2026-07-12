"""
Cascade HQ: the hub the rest of the base-building layer hangs off of.

  * PlayerBase.hq_level gates two things: which harvesters/shrines/shop
    listings are unlocked at all (`unlock_hq_level` on each template), and
    how high any harvester/shrine can currently be leveled
    (hq_config.building_level_cap).
  * Upgrading the HQ itself requires every harvester AND shrine unlocked at
    the CURRENT hq_level to be owned and sitting at that level's building
    cap (or their own lower max_level) -- see `missing_hq_requirements`.
    Once that's true, the HQ upgrade spends its own gold+material cost and
    raises the cap, which is what makes further harvester/shrine upgrades
    (and, via unlock_hq_level, entirely new ones) possible again.
  * Shrines grant a party-wide stat bonus applied at battle-build time via
    `apply_shrine_bonuses` -- see bot/services/combat_service.py.
  * The shop is stateless catalog + optional daily purchase limits; no
    leveling, so it never factors into HQ upgrade requirements.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.economy_model import HarvesterTemplate, PlayerHarvester
from bot.database.models.hq_model import (
    PlayerBase,
    PlayerShopPurchase,
    PlayerShrine,
    ShopListing,
    ShrineTemplate,
)
from bot.game.combat.combatant import STAT_KEYS
from bot.game.economy.hq_config import (
    HQ_LEVEL_CONFIG,
    SHOP_LISTINGS,
    SHRINE_TEMPLATES,
    building_level_cap,
    is_max_hq_level,
    upgrade_requirements,
)
from bot.services import harvester_service
from bot.services.currency_service import add_currency, spend_currency

DAILY_LIMIT_WINDOW = dt.timedelta(hours=24)


# ----------------------------------------------------------------------
# Seeding
# ----------------------------------------------------------------------

def ensure_base_catalog_seeded(db) -> None:
    """Upserts ShrineTemplate + ShopListing rows from hq_config. Safe to
    call every startup, same pattern as the harvester/item/lootbox seeders."""
    for data in SHRINE_TEMPLATES:
        existing = db.query(ShrineTemplate).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(ShrineTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)

    for data in SHOP_LISTINGS:
        existing = db.query(ShopListing).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(ShopListing(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)

    db.commit()


# ----------------------------------------------------------------------
# HQ
# ----------------------------------------------------------------------

def get_or_create_base(db, player) -> PlayerBase:
    base = db.get(PlayerBase, player.id)
    if base is None:
        base = PlayerBase(player_id=player.id, hq_level=1)
        db.add(base)
        db.commit()
        db.refresh(base)
    return base


def get_hq_level(db, player) -> int:
    return get_or_create_base(db, player).hq_level


def missing_hq_requirements(db, player) -> list[str]:
    """Human-readable list of what's still standing between the player and
    their next HQ upgrade. Empty list means they're ready."""
    base = get_or_create_base(db, player)
    if is_max_hq_level(base.hq_level):
        return ["Cascade HQ is already at its maximum level."]

    cap = building_level_cap(base.hq_level)
    missing: list[str] = []

    owned_harvesters = {h.template_id: h for h in harvester_service.list_player_harvesters(db, player.id)}
    for template in harvester_service.list_templates(db):
        if template.unlock_hq_level > base.hq_level:
            continue
        target = min(template.max_level, cap)
        owned = owned_harvesters.get(template.id)
        if owned is None:
            missing.append(f"Build {template.name}")
        elif owned.level < target:
            missing.append(f"Upgrade {template.name} to level {target} (currently {owned.level})")

    owned_shrines = {s.template_id: s for s in list_player_shrines(db, player.id)}
    for template in list_shrine_templates(db):
        if template.unlock_hq_level > base.hq_level:
            continue
        target = min(template.max_level, cap)
        owned = owned_shrines.get(template.id)
        if owned is None:
            missing.append(f"Build {template.name}")
        elif owned.level < target:
            missing.append(f"Upgrade {template.name} to level {target} (currently {owned.level})")

    return missing


def can_upgrade_hq(db, player) -> tuple[bool, list[str]]:
    missing = missing_hq_requirements(db, player)
    base = get_or_create_base(db, player)
    if is_max_hq_level(base.hq_level):
        return False, missing
    return (len(missing) == 0), missing


def upgrade_hq(db, player) -> tuple[bool, str]:
    base = get_or_create_base(db, player)
    if is_max_hq_level(base.hq_level):
        return False, "Cascade HQ is already at its maximum level."

    ready, missing = can_upgrade_hq(db, player)
    if not ready:
        preview = "; ".join(missing[:3])
        more = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
        return False, f"Not ready to upgrade HQ -- still need: {preview}{more}"

    cost = upgrade_requirements(base.hq_level)["upgrade_cost"]
    for currency, amount in cost.items():
        if getattr(player, currency) < amount:
            return False, f"Not enough {currency} (need {amount})."

    for currency, amount in cost.items():
        spend_currency(db, player, currency, amount)

    base.hq_level += 1
    db.commit()
    return True, f"Cascade HQ upgraded to level {base.hq_level}!"


# ----------------------------------------------------------------------
# Shrines
# ----------------------------------------------------------------------

def list_shrine_templates(db) -> list[ShrineTemplate]:
    return db.query(ShrineTemplate).all()


def list_player_shrines(db, player_id: int) -> list[PlayerShrine]:
    return db.query(PlayerShrine).filter_by(player_id=player_id).all()


def get_shrine_upgrade_cost(template: ShrineTemplate, level: int) -> int:
    return round(template.base_upgrade_cost * (template.upgrade_cost_growth ** (level - 1)))


def shrine_effective_max_level(template: ShrineTemplate, hq_level: int) -> int:
    return min(template.max_level, building_level_cap(hq_level))


def shrine_bonus_at_level(template: ShrineTemplate, level: int) -> float:
    return template.base_bonus_per_level * level


def build_shrine(db, player, template_id: int, hq_level: int) -> tuple[bool, str]:
    template = db.get(ShrineTemplate, template_id)
    if template is None:
        return False, "No such shrine."
    if hq_level < template.unlock_hq_level:
        return False, (
            f"{template.name} requires Cascade HQ level {template.unlock_hq_level} "
            f"(currently level {hq_level})."
        )

    existing = (
        db.query(PlayerShrine)
        .filter_by(player_id=player.id, template_id=template_id)
        .first()
    )
    if existing is not None:
        return False, f"You already have a {template.name}."

    if not spend_currency(db, player, "gold", template.build_cost_gold):
        return False, f"Not enough gold (need {template.build_cost_gold})."

    shrine = PlayerShrine(player_id=player.id, template_id=template_id, level=1)
    db.add(shrine)
    db.commit()
    return True, f"Built {template.name}!"


def upgrade_shrine(db, player, shrine: PlayerShrine, hq_level: int) -> tuple[bool, str]:
    template = shrine.template
    if shrine.level >= template.max_level:
        return False, f"{template.name} is already at max level."

    cap = shrine_effective_max_level(template, hq_level)
    if shrine.level >= cap:
        return False, (
            f"{template.name} is at its Cascade HQ level cap ({cap}). "
            f"Upgrade Cascade HQ to raise the cap."
        )

    cost = get_shrine_upgrade_cost(template, shrine.level)
    if not spend_currency(db, player, template.upgrade_currency, cost):
        return False, f"Not enough {template.upgrade_currency} (need {cost})."

    shrine.level += 1
    db.commit()
    return True, f"{template.name} upgraded to level {shrine.level} for {cost} {template.upgrade_currency}."


def apply_shrine_bonuses(db, player, combatants: list) -> None:
    """Mutates each Combatant's base_stats in place, adding every built
    shrine's bonus on top of that combatant's own (character + gear)
    stats. Percent shrines are computed against each combatant's own
    current value of the stat -- consistent with how gear percent
    substats never compound with each other."""
    shrines = list_player_shrines(db, player.id)
    if not shrines:
        return

    for shrine in shrines:
        template = shrine.template
        if template.stat not in STAT_KEYS:
            continue
        bonus = shrine_bonus_at_level(template, shrine.level)
        for combatant in combatants:
            if not combatant.is_player:
                continue
            if template.bonus_type == "percent":
                combatant.base_stats[template.stat] += (
                    combatant.base_stats.get(template.stat, 0) * bonus / 100
                )
            else:
                combatant.base_stats[template.stat] = (
                    combatant.base_stats.get(template.stat, 0) + bonus
                )


# ----------------------------------------------------------------------
# Shop
# ----------------------------------------------------------------------

def list_shop_listings(db, hq_level: int) -> list[ShopListing]:
    return [
        listing for listing in db.query(ShopListing).all()
        if listing.unlock_hq_level <= hq_level
    ]


def _get_or_create_purchase_row(db, player_id: int, listing_id: int) -> PlayerShopPurchase:
    row = (
        db.query(PlayerShopPurchase)
        .filter_by(player_id=player_id, listing_id=listing_id)
        .first()
    )
    now = dt.datetime.now(dt.timezone.utc)
    if row is None:
        row = PlayerShopPurchase(
            player_id=player_id, listing_id=listing_id,
            purchased_count=0, window_started_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    started = row.window_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=dt.timezone.utc)
    if now - started >= DAILY_LIMIT_WINDOW:
        row.purchased_count = 0
        row.window_started_at = now
        db.commit()
    return row


def purchase_listing(db, player, listing_id: int, hq_level: int) -> tuple[bool, str]:
    listing = db.get(ShopListing, listing_id)
    if listing is None:
        return False, "No such shop listing."
    if hq_level < listing.unlock_hq_level:
        return False, (
            f"{listing.name} requires Cascade HQ level {listing.unlock_hq_level} "
            f"(currently level {hq_level})."
        )

    if listing.daily_limit > 0:
        purchase_row = _get_or_create_purchase_row(db, player.id, listing_id)
        if purchase_row.purchased_count >= listing.daily_limit:
            return False, f"You've already bought {listing.name} the max {listing.daily_limit} times today."
    else:
        purchase_row = None

    if not spend_currency(db, player, listing.cost_currency, listing.cost_amount):
        return False, f"Not enough {listing.cost_currency} (need {listing.cost_amount})."

    if listing.kind == "exchange":
        add_currency(db, player, listing.reward_currency, listing.reward_amount)
        result_text = f"Received {listing.reward_amount} {listing.reward_currency}."
    elif listing.kind == "item":
        from bot.database.models.equipment_model import ItemTemplate
        from bot.game.loot.generator import LootGenerator

        item_template = db.query(ItemTemplate).filter_by(name=listing.item_template_name).first()
        if item_template is None:
            # Refund -- catalog misconfiguration shouldn't eat the player's currency.
            add_currency(db, player, listing.cost_currency, listing.cost_amount)
            return False, f"{listing.name} is temporarily unavailable."
        item = LootGenerator().generate_item(item_template, player_id=player.id, item_level=listing.item_level)
        db.add(item)
        db.commit()
        result_text = f"Received {item.display_name}!"
    else:
        add_currency(db, player, listing.cost_currency, listing.cost_amount)
        return False, f"{listing.name} has an unknown listing type."

    if purchase_row is not None:
        purchase_row.purchased_count += 1
        db.commit()

    return True, f"Bought {listing.name}. {result_text}"
