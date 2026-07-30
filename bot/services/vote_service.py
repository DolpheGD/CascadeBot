"""
/vote command logic: one claim per VOTE_COOLDOWN_HOURS (matching top.gg's
own 12h vote cooldown), with a streak that advances once per claimed vote
and survives as long as the next claim lands within
VOTE_STREAK_GRACE_HOURS.

Same shape as daily_service.claim_daily on purpose -- the two are sibling
recurring-reward flows and should stay easy to compare -- with one extra
wrinkle that /daily doesn't have:

    Top.gg's API cannot identify an individual vote. Its check endpoint
    answers only "has this user voted in the last 12 hours?", so after a
    player votes and claims, that endpoint keeps saying "yes" for the rest
    of the window. Player.last_vote_claimed_at is therefore the real guard
    against redeeming one vote repeatedly -- not the API. claim_vote
    checks the cooldown BEFORE anything is granted, and the cog checks
    has_voted() before calling in here at all.

The network call itself lives in bot/services/topgg_client.py; everything
in this module is synchronous and DB-only, so it stays as testable as the
rest of the service layer.
"""

from __future__ import annotations

import datetime as dt

from bot.game.economy.vote_config import (
    VOTE_COOLDOWN_HOURS,
    VOTE_STREAK_GRACE_HOURS,
    compute_vote_currency,
    compute_vote_lootboxes,
    compute_vote_materials,
    next_milestone_in,
)
from bot.services import lootbox_service, quest_service
from bot.services.currency_service import add_currency
from bot.utils.time_utils import as_utc, utcnow


class VoteOnCooldown(Exception):
    """Raised when a player tries to claim again inside the 12h window
    they've already been paid for."""

    def __init__(self, time_remaining: dt.timedelta):
        self.time_remaining = time_remaining
        super().__init__(f"Vote reward on cooldown for {time_remaining}")


def cooldown_remaining(player) -> dt.timedelta | None:
    """How long until this player can claim a vote reward again, or None
    if they can claim right now. Read-only -- safe for the /vote embed to
    call before deciding what to show."""
    if player.last_vote_claimed_at is None:
        return None
    elapsed = utcnow() - as_utc(player.last_vote_claimed_at)
    remaining = dt.timedelta(hours=VOTE_COOLDOWN_HOURS) - elapsed
    return remaining if remaining > dt.timedelta(0) else None


def streak_expires_at(player) -> dt.datetime | None:
    """When an unbroken streak lapses back to zero, or None if the player
    has never claimed. Shown on the /vote embed so a streak worth keeping
    has a visible deadline."""
    if player.last_vote_claimed_at is None:
        return None
    return as_utc(player.last_vote_claimed_at) + dt.timedelta(hours=VOTE_STREAK_GRACE_HOURS)


def peek_next_reward(player) -> dict:
    """What the player's NEXT claim would pay out, without granting
    anything -- used to show the reward preview on /vote before they've
    voted. Assumes the streak survives, which is what the embed's
    'claim before <timestamp>' line is telling them to ensure."""
    streak = _next_streak(player)
    shards, gold, reroll_tokens = compute_vote_currency(streak)
    return {
        "streak": streak,
        "shards": shards,
        "gold": gold,
        "reroll_tokens": reroll_tokens,
        "materials": compute_vote_materials(streak),
        "lootbox_tiers": compute_vote_lootboxes(streak),
        "milestone_in": next_milestone_in(streak),
    }


def _next_streak(player) -> int:
    """What vote_streak would become on a claim right now: +1 if the
    grace window is still open (or this is their first ever vote), else
    back to 1."""
    if player.last_vote_claimed_at is None:
        return 1
    elapsed = utcnow() - as_utc(player.last_vote_claimed_at)
    if elapsed <= dt.timedelta(hours=VOTE_STREAK_GRACE_HOURS):
        return player.vote_streak + 1
    return 1


def claim_vote(db, player, is_weekend: bool = False) -> dict:
    """Pays out a confirmed top.gg vote. The CALLER is responsible for
    having verified with topgg_client.has_voted() that a vote actually
    happened -- this function only enforces that we haven't already paid
    for the current window.

    Raises VoteOnCooldown if claimed too recently. Returns a dict of
    everything granted, for the cog to render.
    """
    remaining = cooldown_remaining(player)
    if remaining is not None:
        raise VoteOnCooldown(remaining)

    streak = _next_streak(player)
    shards, gold, reroll_tokens = compute_vote_currency(streak, is_weekend=is_weekend)
    materials = compute_vote_materials(streak)
    lootbox_tiers = compute_vote_lootboxes(streak)

    # Commit the streak/timestamp bookkeeping BEFORE handing anything out.
    # If a grant below were to fail partway, the player has still had
    # their claim recorded and can't replay the whole payout by
    # re-running /vote -- the same ordering claim_daily uses.
    player.vote_streak = streak
    player.total_votes += 1
    player.last_vote_claimed_at = utcnow()
    db.commit()

    if shards:
        add_currency(db, player, "shards", shards)
    if gold:
        add_currency(db, player, "gold", gold)
    if reroll_tokens:
        add_currency(db, player, "reroll_tokens", reroll_tokens)
    for material, amount in materials.items():
        add_currency(db, player, material, amount)
    for tier in lootbox_tiers:
        lootbox_service.grant_lootbox(db, player, tier, quantity=1)

    quest_service.record_progress(db, player, "vote")

    return {
        "streak": streak,
        "total_votes": player.total_votes,
        "shards": shards,
        "gold": gold,
        "reroll_tokens": reroll_tokens,
        "materials": materials,
        "lootbox_tiers": lootbox_tiers,
        "is_weekend": is_weekend,
        "milestone_in": next_milestone_in(streak),
    }
