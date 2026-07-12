"""
Mailbox: a single per-player building (no template catalog, no buying --
see bot/database/models/hq_model.py::PlayerMailbox) that brews one package
of basic supplies every 30min-1hr and can be leveled up for better rewards.
"""

from __future__ import annotations

import datetime as dt
import random

from bot.database.models.hq_model import PlayerMailbox
from bot.game.economy.mailbox_config import (
    is_max_level,
    roll_next_package_delay,
    roll_package,
    upgrade_cost,
)
from bot.services.currency_service import add_currency, spend_currency


def get_or_create_mailbox(db, player) -> PlayerMailbox:
    mailbox = db.get(PlayerMailbox, player.id)
    if mailbox is None:
        mailbox = PlayerMailbox(
            player_id=player.id,
            level=1,
            next_package_at=dt.datetime.now(dt.timezone.utc) + roll_next_package_delay(),
        )
        db.add(mailbox)
        db.commit()
        db.refresh(mailbox)
    return mailbox


def _aware(when: dt.datetime) -> dt.datetime:
    return when if when.tzinfo is not None else when.replace(tzinfo=dt.timezone.utc)


def is_ready(mailbox: PlayerMailbox) -> bool:
    return dt.datetime.now(dt.timezone.utc) >= _aware(mailbox.next_package_at)


def time_until_ready(mailbox: PlayerMailbox) -> dt.timedelta:
    remaining = _aware(mailbox.next_package_at) - dt.datetime.now(dt.timezone.utc)
    return remaining if remaining > dt.timedelta(0) else dt.timedelta(0)


def collect_mailbox(db, player, rng: random.Random | None = None) -> tuple[bool, str, dict[str, int]]:
    """Returns (collected, message, rewards). rewards is {} if nothing was
    collected (mailbox not ready yet)."""
    mailbox = get_or_create_mailbox(db, player)
    if not is_ready(mailbox):
        remaining = time_until_ready(mailbox)
        minutes = max(1, int(remaining.total_seconds() // 60))
        return False, f"Your next package isn't ready yet -- check back in {minutes}m.", {}

    rewards = roll_package(mailbox.level, rng=rng)
    for currency, amount in rewards.items():
        add_currency(db, player, currency, amount)

    mailbox.next_package_at = dt.datetime.now(dt.timezone.utc) + roll_next_package_delay(rng=rng)
    db.commit()

    if not rewards:
        return True, "The package was empty this time -- better luck next delivery!", {}

    parts = ", ".join(f"{amount} {currency}" for currency, amount in rewards.items())
    return True, f"A package arrived: {parts}!", rewards


def get_mailbox_upgrade_cost(mailbox: PlayerMailbox) -> dict[str, int] | None:
    return upgrade_cost(mailbox.level)


def upgrade_mailbox(db, player) -> tuple[bool, str]:
    mailbox = get_or_create_mailbox(db, player)
    if is_max_level(mailbox.level):
        return False, "Your mailbox is already at max level."

    cost = upgrade_cost(mailbox.level)
    for currency, amount in cost.items():
        if getattr(player, currency) < amount:
            cost_text = ", ".join(f"{amt} {cur}" for cur, amt in cost.items())
            return False, f"Not enough resources (need {cost_text})."

    for currency, amount in cost.items():
        spend_currency(db, player, currency, amount)

    mailbox.level += 1
    db.commit()
    return True, f"Mailbox upgraded to level {mailbox.level}! Packages will be a little better from now on."
