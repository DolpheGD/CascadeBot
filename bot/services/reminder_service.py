"""
Opt-in reminders, sent as DMs by the nightly scheduler.

THE RISK THIS IS BUILT AROUND. A bot that DMs people gets blocked and
reported, and the report is filed against the bot rather than the
feature. Discord acts on that. So every rule below exists to make it
impossible for this to become the reason somebody reports the bot, even
if the content is fine:

  1. OFF BY DEFAULT, for everybody, including players who already
     existed when this shipped. Turning it on for the existing player
     base would mean unsolicited DMs to every one of them on night one.

  2. AT MOST ONE MESSAGE A DAY, enforced against last_reminder_at rather
     than trusting the scheduler to fire once. A loop that gets restarted
     four times in an evening must not send four DMs.

  3. NOTHING TO SAY MEANS NOTHING SENT. A reminder that arrives to
     report that nothing is waiting is the exact thing people mute. The
     content is computed first and the send is skipped if it is empty.

  4. A FAILED SEND DISABLES THE PLAYER, permanently, after
     MAX_FAILURES. Discord raises Forbidden when DMs are closed or the
     bot is blocked. Without this the sweep would retry that same person
     every night forever -- which is not merely wasteful, it is the
     precise behaviour that gets a bot reported.

  5. IT DOES NOT NAG THE ACTIVE. Somebody who played today does not need
     a reminder; the threshold is deliberately generous.

WHY IT SHARES away_service's READINGS. The DM and the welcome-back screen
answer the same question -- what is waiting for you -- and if they used
separate logic they would drift and start disagreeing. One player would
be told their harvesters are full and then open the game to be told they
are not. So the summary is computed in exactly one place and this module
formats it.
"""

from __future__ import annotations

import datetime as dt

from bot.utils.logger import get_logger
from bot.utils.time_utils import as_utc

logger = get_logger(__name__)

# Don't remind anybody who has played more recently than this.
QUIET_AFTER_HOURS = 20

# Consecutive failed DMs before a player is switched off for good.
# One is nearly enough -- Forbidden means "closed or blocked", which does
# not resolve itself -- but two absorbs a transient API error without
# costing somebody their reminders.
MAX_FAILURES = 2


def eligible_players(db) -> list:
    """Everyone who has opted in, is due, and has something waiting."""
    from bot.database.models.player_model import Player

    now = dt.datetime.now(dt.timezone.utc)
    candidates = (
        db.query(Player)
        .filter(Player.reminders_enabled.is_(True))
        .filter(Player.reminder_failures < MAX_FAILURES)
        .all()
    )

    due = []
    for player in candidates:
        # Rule 2: one a day, measured, not assumed.
        if player.last_reminder_at is not None:
            since = (now - as_utc(player.last_reminder_at)).total_seconds() / 3600
            if since < 20:
                continue
        # Rule 5: don't nag somebody who is playing.
        if player.last_seen_at is not None:
            idle = (now - as_utc(player.last_seen_at)).total_seconds() / 3600
            if idle < QUIET_AFTER_HOURS:
                continue
        due.append(player)
    return due


def compose(db, player) -> str | None:
    """The reminder text, or None if there is nothing worth sending."""
    from bot.services import away_service

    summary = away_service.summarise(db, player)
    if not summary:
        return None
    # Only the things that are actively costing the player something.
    # "Your daily is ready" alone is not worth a DM -- it is true most
    # mornings and turns the reminder into noise.
    if not summary.get("urgent"):
        return None

    body = "\n".join(f"• {line}" for line in summary["lines"])
    return (
        f"**CascadeBot** — you've been away {summary['away_text']}, and "
        f"some things are going to waste:\n\n{body}\n\n"
        f"*Turn these off any time with `/notifications`.*"
    )


async def send_due_reminders(bot) -> tuple[int, int]:
    """Send today's reminders. Returns (sent, auto-disabled).

    Never raises: it runs from a scheduled loop, and an exception there
    cancels the loop permanently and silently.
    """
    import discord

    from bot.database.session import SessionLocal

    sent = 0
    disabled = 0
    db = SessionLocal()
    try:
        for player in eligible_players(db):
            try:
                message = compose(db, player)
                if not message:
                    continue  # rule 3

                user = bot.get_user(player.id) or await bot.fetch_user(player.id)
                await user.send(message)

                player.last_reminder_at = dt.datetime.now(dt.timezone.utc)
                player.reminder_failures = 0
                db.commit()
                sent += 1

            except (discord.Forbidden, discord.NotFound):
                # Closed DMs, blocked bot, or a deleted account. This
                # does not get better by trying again tomorrow.
                player.reminder_failures = int(player.reminder_failures or 0) + 1
                if player.reminder_failures >= MAX_FAILURES:
                    player.reminders_enabled = False
                    disabled += 1
                    logger.info("Reminders auto-disabled for %s (DMs unreachable)",
                                player.id)
                db.commit()
            except Exception:
                logger.exception("Reminder failed for player %s", player.id)
    finally:
        db.close()
    return sent, disabled
