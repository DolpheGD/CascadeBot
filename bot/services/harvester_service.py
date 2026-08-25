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
from bot.utils.time_utils import as_utc


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


# ----------------------------------------------------------------------
# STORAGE -- how long a harvester keeps accruing before it fills up
#
# `max_accumulation_hours` used to be the whole answer: a flat 8 hours,
# forever, for every harvester at every level. Two problems with that,
# and the second is the one that matters.
#
#   * 8 hours is shorter than a night's sleep, so the intended pattern --
#     check in, collect, come back later -- lost you production every
#     single time unless you happened to log in twice a day.
#
#   * more importantly it never CHANGED. Levelling a harvester raised the
#     rate but not the tank, so the fuller cap filled faster, and past a
#     certain level upgrading actively shortened how long you could be
#     away. A progression system whose reward is a tighter leash is
#     working against itself.
#
# So capacity now grows from three sources the player can act on, all of
# them visible in the harvester panel:
#
#   1. the template's own base hours (raised to 12, past a night)
#   2. +STORAGE_HOURS_PER_LEVEL per harvester level -- levelling the
#      harvester enlarges the tank as well as the tap
#   3. the Research Lab's Logistics branch, via the
#      `harvester_storage_hours` perk
# ----------------------------------------------------------------------

# Each harvester level adds this many hours of storage. At 0.5, a level-20
# harvester holds 12 + 9.5 = 21.5 hours before the lab touches it -- a
# full day's absence with a little slack, which is the shape the pattern
# wanted in the first place.
STORAGE_HOURS_PER_LEVEL = 0.5


def storage_hours(db, harvester: PlayerHarvester) -> float:
    """Total hours this harvester can bank before it stops accruing."""
    from bot.services import research_service

    hours = harvester.template.max_accumulation_hours
    hours += STORAGE_HOURS_PER_LEVEL * (harvester.level - 1)
    hours += research_service.perk_value(
        db, harvester.player_id, "harvester_storage_hours"
    ) or 0
    return hours


def storage_capacity(db, harvester: PlayerHarvester) -> int:
    """How many units this harvester holds when completely full -- the
    number the panel shows as the denominator."""
    rate = get_production_rate(harvester.template, harvester.level)
    return round(rate * storage_hours(db, harvester))


def pending_production(db, harvester: PlayerHarvester) -> int:
    """How much this harvester is holding right now, uncollected.

    A READ -- it does not reset the clock or grant anything, so it is
    safe to call anywhere for display.

    Split out of collect_harvester so the number the player is SHOWN and
    the number they are PAID come from one place. Computing it twice is
    the failure this codebase hits most often, and it is especially nasty
    here: the two would agree until somebody retuned the Logistics
    research perk, and then the panel would quietly promise a figure the
    collection did not deliver.
    """
    now = dt.datetime.now(dt.timezone.utc)
    elapsed_hours = (now - as_utc(harvester.last_collected_at)).total_seconds() / 3600
    elapsed_hours = min(elapsed_hours, storage_hours(db, harvester))
    elapsed_hours = max(elapsed_hours, 0.0)

    amount = round(get_production_rate(harvester.template, harvester.level) * elapsed_hours)

    # Research Lab's Logistics branch (harvester_percent).
    from bot.services import research_service
    yield_bonus = research_service.perk_value(db, harvester.player_id, "harvester_percent")
    if yield_bonus:
        amount = int(round(amount * (1 + yield_bonus / 100)))
    return amount


def collect_harvester(db, harvester: PlayerHarvester) -> int:
    """Adds accrued production to the owner's balance (or grants XP), resets the clock.
    Returns the amount collected (0 if nothing had accrued)."""
    template = harvester.template
    now = dt.datetime.now(dt.timezone.utc)

    amount = pending_production(db, harvester)

    harvester.last_collected_at = now
    db.commit()

    if amount > 0:
        # Special-case XP: harvesters that produce "xp" should grant XP to
        # the player's squad rather than treating it as a player-held
        # currency. This keeps the existing currency system untouched.
        if template.currency == "xp":
            from bot.services import character_service, combat_service

            squad = character_service.get_squad(db, harvester.player)
            combat_service.apply_character_xp(db, squad, amount, player=harvester.player)
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
