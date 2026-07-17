"""
Passive-income harvesters: buy one, it accrues currency over real time,
collect it (capped so idling too long doesn't stockpile forever), and
spend gold to upgrade it for a higher rate.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.economy_model import HarvesterTemplate, PlayerHarvester
from bot.game.economy.harvester_config import HARVESTER_TEMPLATES
from bot.game.economy.hq_config import building_level_cap
from bot.services import quest_service
from bot.services.currency_service import add_currency, format_currency, spend_currency


def ensure_harvester_templates_seeded(db) -> None:
    """Upserts HARVESTER_TEMPLATES into the DB. Safe to call every startup."""
    for data in HARVESTER_TEMPLATES:
        existing = db.query(HarvesterTemplate).filter_by(name=data["name"]).first()
        if existing is None:
            db.add(HarvesterTemplate(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
    db.commit()


def list_templates(db) -> list[HarvesterTemplate]:
    return db.query(HarvesterTemplate).all()


def list_player_harvesters(db, player_id: int) -> list[PlayerHarvester]:
    return db.query(PlayerHarvester).filter_by(player_id=player_id).all()


def get_upgrade_cost(template: HarvesterTemplate, level: int) -> int:
    return round(template.base_upgrade_cost * (template.upgrade_cost_growth ** (level - 1)))


def effective_max_level(template: HarvesterTemplate, hq_level: int) -> int:
    """The level this harvester can currently reach -- the lower of its own
    absolute `max_level` and the level cap Cascade HQ currently allows.
    Upgrading further requires upgrading the HQ first."""
    return min(template.max_level, building_level_cap(hq_level))


def get_production_rate(template: HarvesterTemplate, level: int) -> float:
    """Rate scales as level ** level_scaling_exponent -- 1.0 (most
    harvesters) is the old linear behavior; lower (the Shard Well) means
    each additional level adds progressively less, so Shards stay rare
    relative to gold even at max level."""
    return template.base_rate_per_hour * (level ** template.level_scaling_exponent)


def buy_harvester(db, player, template_id: int, hq_level: int = 1) -> tuple[bool, str, PlayerHarvester | None]:
    template = db.get(HarvesterTemplate, template_id)
    if template is None:
        return False, "No such harvester.", None

    if hq_level < template.unlock_hq_level:
        return False, (
            f"{template.name} requires Cascade HQ level {template.unlock_hq_level} "
            f"(currently level {hq_level})."
        ), None

    existing = (
        db.query(PlayerHarvester)
        .filter_by(player_id=player.id, template_id=template_id)
        .first()
    )
    if existing is not None:
        return False, f"You already own a {template.name}.", None

    if template.unlock_cost > 0:
        if not spend_currency(db, player, template.unlock_currency, template.unlock_cost):
            return False, f"Not enough {format_currency(template.unlock_currency, template.unlock_cost)}.", None

    harvester = PlayerHarvester(
        player_id=player.id,
        template_id=template_id,
        level=1,
        last_collected_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(harvester)
    db.commit()
    db.refresh(harvester)
    quest_service.record_progress(db, player, "buy_harvester")
    return True, f"Acquired {template.name}!", harvester


def collect_harvester(db, harvester: PlayerHarvester) -> int:
    """Adds accrued production to the owner's balance (or grants XP), resets the clock.
    Returns the amount collected (0 if nothing had accrued)."""
    template = harvester.template
    now = dt.datetime.now(dt.timezone.utc)

    last_collected = harvester.last_collected_at
    if last_collected.tzinfo is None:
        last_collected = last_collected.replace(tzinfo=dt.timezone.utc)

    elapsed_hours = (now - last_collected).total_seconds() / 3600
    elapsed_hours = min(elapsed_hours, template.max_accumulation_hours)
    elapsed_hours = max(elapsed_hours, 0.0)

    rate = get_production_rate(template, harvester.level)
    amount = round(rate * elapsed_hours)

    harvester.last_collected_at = now
    db.commit()

    if amount > 0:
        # Special-case XP: harvesters that produce "xp" should grant XP to
        # the player's squad rather than treating it as a player-held
        # currency. This keeps the existing currency system untouched.
        if template.currency == "xp":
            from bot.services import character_service, combat_service

            squad = character_service.get_squad(db, harvester.player)
            combat_service.apply_character_xp(db, squad, amount)
        else:
            add_currency(db, harvester.player, template.currency, amount)

        quest_service.record_progress(db, harvester.player, "collect_harvester")

    return amount


def upgrade_harvester(db, player, harvester: PlayerHarvester, hq_level: int = 1) -> tuple[bool, str]:
    template = harvester.template
    if harvester.level >= template.max_level:
        return False, f"{template.name} is already at max level."

    cap = effective_max_level(template, hq_level)
    if harvester.level >= cap:
        return False, (
            f"{template.name} is at its Cascade HQ level cap ({cap}). "
            f"Upgrade Cascade HQ to raise the cap."
        )

    cost = get_upgrade_cost(template, harvester.level)
    if not spend_currency(db, player, "gold", cost):
        return False, f"Not enough {format_currency('gold', cost)}."

    harvester.level += 1
    db.commit()
    return True, f"{template.name} upgraded to level {harvester.level} for {format_currency('gold', cost)}."
