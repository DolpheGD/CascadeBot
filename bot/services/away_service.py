"""
What happened while the player was away.

THE PROBLEM THIS ANSWERS. Six systems in this game accrue or expire on a
clock, and every one of them is invisible when nobody is looking:

    harvesters        fill in 12-16h and then WASTE everything after
    domain energy     fills from empty in 14h and then wastes regen
    daily reward      resets nightly; the streak breaks if missed
    vote window       opens every 12h
    challenge cycle   banks only the LAST completed cycle
    raids             run on a server-wide timer

A player who takes a weekend off loses harvester output, their streak,
and possibly a whole challenge cycle -- and the game never mentions any
of it. They cannot even find out afterwards. The first symptom of "your
buffers have been full since Friday" is a number that is lower than it
should be, weeks later.

WHY A SUMMARY AND NOT A NOTIFICATION. This module sends nothing. It reads
state and describes it, and the caller renders it on the next screen the
player opens anyway. That makes it free of every risk a notification
carries -- nothing to opt into, nothing to block, no way to annoy
somebody who is not currently playing.

Reminders (bot/services/reminder_service.py) are the opt-in half, and
they deliberately reuse the same readings so the DM and the welcome-back
screen can never disagree about what is waiting.

IT IS A READ. Nothing here writes, collects, claims or grants. A summary
that quietly collected the player's harvesters on their behalf would be
taking a decision away from them -- and would make the numbers it reports
wrong the moment it did.
"""

from __future__ import annotations

import datetime as dt

from bot.utils.time_utils import as_utc

# Below this, there is nothing worth saying. Someone who ran a command
# twenty minutes ago does not need to be told what accrued since.
MIN_AWAY = dt.timedelta(hours=6)

# A harvester at or above this fraction of its buffer is "filling up";
# at 1.0 it is already wasting production.
FULL_ENOUGH = 0.9


def _hours_away(player, now: dt.datetime) -> float | None:
    if not player.last_seen_at:
        return None
    return (now - as_utc(player.last_seen_at)).total_seconds() / 3600


def harvester_status(db, player) -> list[dict]:
    """Every harvester, with how full its buffer is.

    Reported per harvester rather than as one total, because "your Shard
    Well is full" is actionable and "you have unclaimed production" is
    not -- the player needs to know which one is wasting output.
    """
    from bot.services import harvester_service

    out = []
    for harvester in harvester_service.list_player_harvesters(db, player.id):
        try:
            capacity = harvester_service.storage_capacity(db, harvester)
            pending = harvester_service.pending_production(db, harvester)
        except Exception:
            # A harvester whose numbers cannot be read must not take the
            # whole welcome-back screen down with it.
            continue
        if capacity <= 0:
            continue
        out.append({
            "name": harvester.template.name,
            "currency": harvester.template.currency,
            "pending": pending,
            "capacity": capacity,
            "fraction": min(1.0, pending / capacity),
        })
    return out


def summarise(db, player) -> dict | None:
    """What is waiting, or None if there is nothing worth a screen.

    Returns None rather than an empty summary so the caller has one
    thing to check. A "while you were away" panel that says "nothing
    happened" is worse than no panel: it costs the same space and
    teaches the player to stop reading it.
    """
    now = dt.datetime.now(dt.timezone.utc)
    hours = _hours_away(player, now)
    if hours is None or hours < MIN_AWAY.total_seconds() / 3600:
        return None

    lines: list[str] = []
    urgent = False

    # ---- harvesters -------------------------------------------------
    overflowing = [h for h in harvester_status(db, player)
                   if h["fraction"] >= FULL_ENOUGH]
    if overflowing:
        urgent = True
        names = ", ".join(h["name"] for h in overflowing[:3])
        more = f" (+{len(overflowing) - 3} more)" if len(overflowing) > 3 else ""
        lines.append(
            f"🏭 **{len(overflowing)} harvester"
            f"{'s are' if len(overflowing) != 1 else ' is'} full** — {names}{more}. "
            f"Anything they produce now is wasted until you collect.")

    # ---- domain energy ----------------------------------------------
    try:
        from bot.services import domain_service
        energy = domain_service.get_current_energy(db, player)
        cap = domain_service.energy_cap(db, player)
        if cap and energy >= cap:
            urgent = True
            lines.append(
                f"⚡ **Domain energy is capped** at {energy}/{cap} — regen is "
                f"being wasted. Spend some on `/domains`.")
    except Exception:
        pass

    # ---- an unclaimed challenge cycle --------------------------------
    #
    # The loudest line on the screen when it applies, because it is the
    # only one where waiting longer destroys the reward outright: the
    # cycle banks one week, so a second missed week overwrites it.
    try:
        from bot.services import challenge_service
        banked, earned = challenge_service.claimable(player)
        if earned:
            urgent = True
            lines.append(
                f"🎁 **Last challenge cycle is unclaimed** — {banked:,} points, "
                f"**{earned[-1][1]}**. Claim it on `/challenge` before this "
                f"cycle ends or it's gone.")
    except Exception:
        pass

    # ---- daily ------------------------------------------------------
    try:
        from bot.utils.time_utils import as_utc as _as_utc
        last_daily = player.last_daily_claimed_at
        if last_daily is None or (now - _as_utc(last_daily)).total_seconds() > 20 * 3600:
            lines.append("📅 **Daily reward is ready** — `/daily`.")
    except Exception:
        pass

    if not lines:
        return None

    return {
        "hours_away": hours,
        "away_text": _describe_absence(hours),
        "lines": lines,
        "urgent": urgent,
    }


def mark_shown(db, player) -> None:
    """Advance last_seen_at now that the player has been told.

    This is the other half of presence_service.touch_last_seen, which
    deliberately refuses to close a long gap. Without this call the
    summary would repeat on every screen forever; without touch_last_seen
    holding the gap open, it would never appear once. Neither is correct
    alone, which is why they are documented in terms of each other.
    """
    player.last_seen_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


def _describe_absence(hours: float) -> str:
    if hours < 48:
        return f"{int(hours)} hours"
    days = hours / 24
    if days < 14:
        return f"{int(days)} days"
    return f"{int(days // 7)} weeks"
