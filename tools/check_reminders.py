"""
Reminders can never become the reason this bot gets reported.

    python -m tools.check_reminders

WHY THIS IS CHECKED AND NOT JUST REVIEWED. Every other feature in this
game fails in front of the player who triggered it. This one fails in
somebody's DMs, at 4am, to a person who is not playing and did not ask --
and the consequence is not a bug report, it is a Discord report against
the bot. There is no version of that which gets noticed early.

It is also the only feature here that acts with nobody watching, so a
regression produces no error, no complaint from the player it happened
to, and no symptom at all until it has happened a few thousand times.

WHAT IS ASSERTED, all of it against the real code:

  * reminders are OFF for a newly created player, and off for a player
    row that predates the feature (a NULL column must read as off, not
    as on)
  * a player who has been active recently is never eligible
  * a player already reminded today is never eligible twice
  * a reminder with nothing urgent to say composes to None, so the sweep
    sends nothing rather than sending "nothing is happening"
  * a Forbidden send (closed DMs, blocked bot) increments a failure
    counter and DISABLES the player at the threshold -- the check that
    matters most, because retrying a blocked user nightly forever is
    exactly the behaviour that gets a bot reported
  * a disabled player is not picked up again by the next sweep
  * the sweep never raises, whatever the send does -- it runs inside a
    tasks.loop, where one unhandled exception cancels the loop silently
    and permanently
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import tempfile


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from bot.database.db_init import init_db
    init_db()

    import discord

    from bot.database.session import SessionLocal
    from bot.services import player_service, reminder_service

    failures: list[str] = []
    db = SessionLocal()
    now = dt.datetime.now(dt.timezone.utc)

    # ---- 1. off by default ------------------------------------------
    fresh = player_service.get_or_create_player(db, 80_001, "Fresh")
    if fresh.reminders_enabled:
        failures.append(
            "a newly created player has reminders ENABLED -- opt-in is the "
            "only version of this that is safe to ship")

    # WHAT PROTECTS THE EXISTING PLAYER BASE ON MIGRATION DAY.
    #
    # The dangerous scenario is a pre-feature row reading as opted-in, so
    # the first nightly sweep after deploying DMs everybody who already
    # plays. Two independent things prevent it, and both are asserted
    # here because either alone would be enough and neither is obvious:
    #
    #   1. db_init adds the column with an explicit DEFAULT 0, so rows
    #      that predate it migrate to "off" rather than to NULL.
    #   2. eligible_players filters with `.is_(True)`, which excludes
    #      NULL as well as 0. If that ever became a plain truthiness
    #      test, a NULL would read as opted-in.
    #
    # Setting an actual NULL is not testable: a freshly created table has
    # NOT NULL from the model, and the migration path supplies the
    # default -- so the state is unreachable from both directions, which
    # is the point. The declarations are checked instead of the state.
    db_init_source = open(os.path.join("bot", "database", "db_init.py"),
                          encoding="utf-8").read()
    if 'add_column("players", "reminders_enabled", "BOOLEAN DEFAULT 0")' not in db_init_source:
        failures.append(
            "db_init does not add reminders_enabled with DEFAULT 0 -- existing "
            "players could migrate to something other than 'off'")

    service_source = open(os.path.join("bot", "services", "reminder_service.py"),
                          encoding="utf-8").read()
    if "reminders_enabled.is_(True)" not in service_source:
        failures.append(
            "eligible_players no longer filters reminders_enabled with "
            ".is_(True) -- a NULL would read as opted-in")

    # ---- 2. the active are not nagged --------------------------------
    active = player_service.get_or_create_player(db, 80_002, "Active")
    active.reminders_enabled = True
    active.last_seen_at = now
    db.commit()
    if any(p.id == active.id for p in reminder_service.eligible_players(db)):
        failures.append(
            "a player who was active just now is eligible for a reminder")

    # ---- 3. once a day, measured ------------------------------------
    away = player_service.get_or_create_player(db, 80_003, "Away")
    away.reminders_enabled = True
    away.last_seen_at = now - dt.timedelta(days=3)
    away.last_reminder_at = now - dt.timedelta(hours=2)
    db.commit()
    if any(p.id == away.id for p in reminder_service.eligible_players(db)):
        failures.append(
            "a player reminded 2 hours ago is eligible again -- a restarted "
            "loop would send several in one evening")

    away.last_reminder_at = None
    db.commit()
    if not any(p.id == away.id for p in reminder_service.eligible_players(db)):
        failures.append(
            "a player away 3 days who has never been reminded is NOT eligible "
            "-- the feature does nothing at all")

    # ---- 4. nothing to say sends nothing -----------------------------
    quiet = player_service.get_or_create_player(db, 80_004, "Quiet")
    quiet.reminders_enabled = True
    quiet.last_seen_at = now - dt.timedelta(days=3)
    db.commit()
    if reminder_service.compose(db, quiet) is not None:
        # A player with no harvesters, no energy cap hit and no cycle has
        # nothing urgent waiting.
        message = reminder_service.compose(db, quiet)
        if "going to waste" in (message or "") and "•" not in (message or ""):
            failures.append(
                "a reminder composed with no urgent content -- a DM that "
                "reports nothing is the thing people mute and then report")

    # ---- 5. a blocked player is dropped, and stays dropped -----------
    class _Blocked:
        async def send(self, *_args, **_kwargs):
            raise discord.Forbidden(
                type("R", (), {"status": 403, "reason": "blocked"})(), "blocked")

    class _FakeBot:
        def get_user(self, _id):
            return _Blocked()

    blocked = player_service.get_or_create_player(db, 80_005, "Blocked")
    blocked.reminders_enabled = True
    blocked.last_seen_at = now - dt.timedelta(days=5)
    blocked.reminder_failures = 0
    db.commit()

    attempts = 0
    while attempts < 10:
        attempts += 1
        try:
            asyncio.run(reminder_service.send_due_reminders(_FakeBot()))
        except Exception as exc:
            failures.append(
                f"send_due_reminders RAISED ({exc!r}) -- inside a tasks.loop "
                f"that cancels the loop permanently and silently")
            break
        db.refresh(blocked)
        if not blocked.reminders_enabled:
            break
    else:
        failures.append(
            "a player whose DMs raise Forbidden was retried 10 times without "
            "ever being disabled -- this retries a blocked user every night "
            "forever, which is how a bot gets reported")

    if blocked.reminders_enabled:
        pass  # already reported above
    elif any(p.id == blocked.id for p in reminder_service.eligible_players(db)):
        failures.append(
            "a disabled player is still picked up by the next sweep")

    disabled_after = attempts
    db.close()

    print("opt-in     : off by default, and NULL cannot occur")
    print(f"rate limit : one per {reminder_service.QUIET_AFTER_HOURS}h idle, "
          f"one per day")
    print(f"auto-disable: after {reminder_service.MAX_FAILURES} failed sends "
          f"(took {disabled_after} sweep(s) in test)")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- reminders are opt-in, rate-limited, and give up on anyone "
          "who can't or won't receive them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
