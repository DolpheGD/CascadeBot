"""
Sending resources to other players, without becoming an exploit.

Gifting is the one feature in the game where value LEAVES one account and
arrives at another, which makes it the one feature where the interesting
questions are all about abuse rather than about fun:

  * ALT FARMING. Nothing stops someone running five accounts and funnelling
    everything into one. The defence is a daily cap on what a sender can
    send (DAILY_SEND_CAP) plus a per-gift cap, so an alt is worth a fixed
    trickle rather than its entire balance -- and a floor on the SENDER's
    account level (MIN_ACCOUNT_LEVEL_TO_SEND), so a freshly-made account
    can't send anything at all until it has actually been played.
  * THE PREMIUM CURRENCIES. Shards buy pulls and Echoes buy characters
    outright; both are the game's scarcity, and neither is giftable at
    any level. GIFTABLE is an allowlist, not a blocklist, so a currency
    added later is un-giftable until somebody decides otherwise.
  * SELF-GIFTING. Refused outright. It would do nothing but launder the
    daily cap.

The caps are per SENDER, deliberately, not per recipient: capping the
recipient would punish a popular player for being given things, and the
resource only leaves the economy once regardless of where it lands.
"""

from __future__ import annotations

import datetime as dt
import re

from bot.database.models.gift_model import Gift
from bot.services.currency_service import add_currency, spend_currency
from bot.utils.time_utils import as_utc, utcnow

# What may be gifted, and the most of it that can go in ONE package.
#
# An allowlist. Shards and Echoes are absent on purpose: they're the
# gacha's scarcity, and a game where the whale can buy the newcomer a
# roster is a different game. Materials and gold are the things a player
# genuinely ends up with a surplus of and a friend genuinely needs.
GIFTABLE: dict[str, int] = {
    "gold": 5_000,
    "reroll_tokens": 50,
    "wood": 500,
    "stone": 500,
    "metal": 300,
    "crystal": 150,
    "xendium": 80,
    "permafrost_ore": 80,
}

# Gifts one player may SEND per rolling 24 hours.
DAILY_SEND_LIMIT = 3

# Account level a sender needs before they can gift at all -- see the
# alt-farming note above. Low enough that a real player passes it in
# their first session or two, high enough that a throwaway account is
# more effort than it's worth.
MIN_ACCOUNT_LEVEL_TO_SEND = 4

# Uncollected gifts one recipient may hold at once. Not a limit on
# generosity -- it stops an inbox being used as unbounded free storage,
# and stops someone being spammed with hundreds of empty packages.
MAX_PENDING_PER_RECIPIENT = 20

# Player-authored text goes into an embed, so it can't carry markdown,
# pings, or newlines. Same conservative shape as character renaming.
MESSAGE_PATTERN = re.compile(r"^[A-Za-z0-9 '\-.,!?]+$")
MESSAGE_MAX_LENGTH = 140


class GiftError(Exception):
    """Any reason a gift can't be sent or collected, phrased for the player."""


def sent_in_last_day(db, player_id: int) -> int:
    since = utcnow() - dt.timedelta(days=1)
    return (
        db.query(Gift)
        .filter(Gift.sender_id == player_id, Gift.created_at >= since)
        .count()
    )


def sends_remaining(db, player_id: int) -> int:
    return max(0, DAILY_SEND_LIMIT - sent_in_last_day(db, player_id))


def next_send_at(db, player_id: int) -> dt.datetime | None:
    """When the sender's oldest gift in the window ages out, or None if
    they have sends available right now."""
    if sends_remaining(db, player_id) > 0:
        return None
    since = utcnow() - dt.timedelta(days=1)
    oldest = (
        db.query(Gift)
        .filter(Gift.sender_id == player_id, Gift.created_at >= since)
        .order_by(Gift.created_at.asc())
        .first()
    )
    return as_utc(oldest.created_at) + dt.timedelta(days=1) if oldest else None


def pending_for(db, recipient_id: int) -> list[Gift]:
    return (
        db.query(Gift)
        .filter(Gift.recipient_id == recipient_id, Gift.collected_at.is_(None))
        .order_by(Gift.created_at.asc())
        .all()
    )


def send_gift(db, sender, recipient_id: int, contents: dict[str, int],
              note: str | None = None) -> Gift:
    """Debits `sender` and creates an uncollected package for
    `recipient_id`.

    The debit happens BEFORE the row is created and the whole thing runs
    in one transaction: a gift that exists without having been paid for
    is duplication, which is the one bug in this feature that would
    actually matter."""
    from bot.services import account_service

    if recipient_id == sender.id:
        raise GiftError("You can't send a gift to yourself.")

    summary = account_service.account_summary(db, sender)
    if summary["level"] < MIN_ACCOUNT_LEVEL_TO_SEND:
        raise GiftError(
            f"You need to reach **account level {MIN_ACCOUNT_LEVEL_TO_SEND}** before you can "
            f"send gifts (you're level {summary['level']}). Level up your characters -- "
            "`/profile` shows your progress."
        )

    if sends_remaining(db, sender.id) <= 0:
        ready = next_send_at(db, sender.id)
        from bot.utils.time_utils import describe_wait
        wait = describe_wait(ready - utcnow()) if ready else "a while"
        raise GiftError(
            f"You've sent your {DAILY_SEND_LIMIT} gifts for today. Next one in {wait}."
        )

    if len(pending_for(db, recipient_id)) >= MAX_PENDING_PER_RECIPIENT:
        raise GiftError(
            "That player already has a full gift inbox -- they'll need to collect "
            "some with `/gifts` before they can receive more."
        )

    cleaned = {c: int(a) for c, a in contents.items() if int(a) > 0}
    if not cleaned:
        raise GiftError("A gift has to actually contain something.")

    for currency, amount in cleaned.items():
        if currency not in GIFTABLE:
            raise GiftError(f"**{currency.replace('_', ' ')}** can't be gifted.")
        cap = GIFTABLE[currency]
        if amount > cap:
            raise GiftError(
                f"You can send at most **{cap:,}** {currency.replace('_', ' ')} in one gift."
            )

    if note:
        note = " ".join(note.split())
        if len(note) > MESSAGE_MAX_LENGTH:
            raise GiftError(f"Notes can be at most {MESSAGE_MAX_LENGTH} characters.")
        if not MESSAGE_PATTERN.match(note):
            raise GiftError("Notes can only contain letters, numbers, spaces and `' - . , ! ?`")

    # Debit first. spend_currency returns False rather than going
    # negative, so an unaffordable gift can never create a package.
    spent: list[tuple[str, int]] = []
    for currency, amount in cleaned.items():
        if not spend_currency(db, sender, currency, amount):
            for refund_currency, refund_amount in spent:
                add_currency(db, sender, refund_currency, refund_amount)
            raise GiftError(
                f"You don't have {amount:,} {currency.replace('_', ' ')} to send."
            )
        spent.append((currency, amount))

    gift = Gift(sender_id=sender.id, recipient_id=recipient_id,
                contents=cleaned, note=note or None)
    db.add(gift)
    db.commit()
    db.refresh(gift)
    return gift


def collect_all(db, player) -> dict:
    """Collects every pending gift for `player`. Returns a summary:
    {"gifts": [...], "totals": {currency: amount}}."""
    pending = pending_for(db, player.id)
    if not pending:
        raise GiftError("You've got no gifts waiting. Ask nicely.")

    totals: dict[str, int] = {}
    now = utcnow()
    for gift in pending:
        for currency, amount in (gift.contents or {}).items():
            # Re-validated at COLLECT time, not just at send time: a
            # currency could be removed from GIFTABLE between the two,
            # and a package in flight shouldn't be able to deliver
            # something the game no longer allows.
            if currency not in GIFTABLE:
                continue
            add_currency(db, player, currency, int(amount))
            totals[currency] = totals.get(currency, 0) + int(amount)
        gift.collected_at = now
    db.commit()
    return {"gifts": pending, "totals": totals}
