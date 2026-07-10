"""
/daily command logic: one claim per DAILY_COOLDOWN_HOURS, with a streak that
survives as long as the player claims again within DAILY_STREAK_GRACE_HOURS
of their last claim (so it's forgiving of a slightly-late claim) but resets
if they go longer than that without claiming.
"""

from __future__ import annotations

import datetime as dt

from bot.game.economy.daily_config import (
    DAILY_COOLDOWN_HOURS,
    DAILY_STREAK_GRACE_HOURS,
    compute_daily_lootboxes,
    compute_daily_reward,
)
from bot.services import lootbox_service
from bot.services.currency_service import add_currency


class DailyOnCooldown(Exception):
    def __init__(self, time_remaining: dt.timedelta):
        self.time_remaining = time_remaining
        super().__init__(f"Daily on cooldown for {time_remaining}")


def claim_daily(db, player) -> dict:
    """
    Claims the player's daily reward. Raises DailyOnCooldown if claimed too
    recently. Returns {"gold": int, "shards": int, "streak": int}.
    """
    now = dt.datetime.now(dt.timezone.utc)

    if player.last_daily_claimed_at is not None:
        last_claimed = player.last_daily_claimed_at
        if last_claimed.tzinfo is None:
            last_claimed = last_claimed.replace(tzinfo=dt.timezone.utc)

        elapsed = now - last_claimed
        if elapsed < dt.timedelta(hours=DAILY_COOLDOWN_HOURS):
            raise DailyOnCooldown(dt.timedelta(hours=DAILY_COOLDOWN_HOURS) - elapsed)

        if elapsed <= dt.timedelta(hours=DAILY_STREAK_GRACE_HOURS):
            player.daily_streak += 1
        else:
            player.daily_streak = 1
    else:
        player.daily_streak = 1

    gold, shards, reroll_tokens = compute_daily_reward(player.daily_streak)
    lootbox_tiers = compute_daily_lootboxes(player.daily_streak)
    player.last_daily_claimed_at = now
    db.commit()

    if gold:
        add_currency(db, player, "gold", gold)
    if shards:
        add_currency(db, player, "shards", shards)
    if reroll_tokens:
        add_currency(db, player, "reroll_tokens", reroll_tokens)
    for tier in lootbox_tiers:
        lootbox_service.grant_lootbox(db, player, tier, quantity=1)

    return {
        "gold": gold, "shards": shards, "reroll_tokens": reroll_tokens, "streak": player.daily_streak,
        "lootbox_tiers": lootbox_tiers,
    }
