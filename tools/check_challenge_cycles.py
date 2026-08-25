"""
Challenge cycles pay out once, on time, and only what was earned.

    python -m tools.check_challenge_cycles

Runs against a real database, because every failure this is looking for
is a STATE failure -- the logic reads fine in isolation and goes wrong
across a boundary, a restart, or a second button press.

THE FAILURE THAT MATTERS MOST IS DOUBLE PAYMENT.

Every Discord message stays live and clickable forever. Last week's
"Claim" button is still sitting in the channel, and pressing it is not an
exotic case -- it is a scroll and a click. finish_hunt shipped with
exactly this hole (it marked the tile read without first checking whether
it already was, so resolving a stale hunt paid twice), which is the
precedent this file exists to stop repeating.

WHAT THIS CHECK DOES NOT CATCH, measured rather than assumed.

Claiming is guarded twice over: `challenge_claimed_cycle` refuses a
second claim, and claim_cycle also zeroes `challenge_banked_points`, so
a repeat finds nothing to pay even if the first guard is gone. Deleting
EITHER one on its own leaves the behaviour correct and this file green.

That was verified by deleting each in turn, and it is worth stating
plainly: a green run here means "a stale button does not pay twice", not
"both guards are intact". Removing both is caught immediately. If one is
ever deliberately removed, the other becomes load-bearing on its own and
this note stops being true.

Also asserted:

  * cycle boundaries land on the same weekday, every time, forever --
    the UI promises a reset day and the arithmetic has to keep it
  * points earned beyond the daily rewarded cap do NOT accrue, because
    every milestone number is sized against that cap
  * a player away for several cycles banks the last one they played,
    rather than nothing (which would eat a week they earned) or all of
    them (which would pay weeks they never claimed)
  * milestones are monotonic -- more points never pays less
"""

from __future__ import annotations

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
    from bot.database.session import SessionLocal
    from bot.services import challenge_service as cs
    from bot.services import player_service
    from bot.game.economy.challenge_config import (
        CYCLE_LENGTH_DAYS,
        MILESTONES,
        POINTS_PER_WIN,
        REWARDED_CHALLENGES_PER_DAY,
    )

    failures: list[str] = []
    db = SessionLocal()

    # squad_power walks the real squad, which builds the avatar on
    # demand from a character template -- so the templates have to exist
    # before any of this touches resolve(). A fresh test database has
    # none, and the failure surfaces four frames down inside
    # character_service as an AttributeError on None, which says nothing
    # about the actual cause.
    from bot.services import character_template_service
    character_template_service.ensure_character_templates_seeded(db)

    # ---- boundaries are stable -------------------------------------
    weekdays = {cs.cycle_ends_at(cs.current_cycle() + n).weekday()
                for n in range(-60, 60)}
    if len(weekdays) != 1:
        failures.append(
            f"cycle boundaries drift across weekdays {sorted(weekdays)} -- "
            f"the UI cannot promise a reset day")

    for n in range(-10, 10):
        index = cs.current_cycle() + n
        span = cs.cycle_ends_at(index) - cs.cycle_ends_at(index - 1)
        if span != dt.timedelta(days=CYCLE_LENGTH_DAYS):
            failures.append(f"cycle {index} spans {span}, not {CYCLE_LENGTH_DAYS}d")

    # ---- milestones are monotonic ----------------------------------
    def payout(points: int) -> int:
        total = 0
        for _, _, rewards in cs.milestones_for(points):
            total += sum(rewards.values())
        return total

    ladder = [payout(p) for p in range(0, MILESTONES[-1][0] + 50, 5)]
    for earlier, later in zip(ladder, ladder[1:]):
        if later < earlier:
            failures.append(
                "milestone payout DECREASES as points rise -- more play pays less")
            break

    # ---- claiming is idempotent ------------------------------------
    player = player_service.get_or_create_player(db, 90_001, "CycleTester")
    cs.sync_cycle(player)
    player.challenge_points = MILESTONES[1][0]
    player.challenge_cycle = cs.current_cycle() - 1
    player.challenge_claimed_cycle = -1
    db.commit()

    before = int(player.gold or 0)
    first = cs.claim_cycle(db, player)
    after_first = int(player.gold or 0)
    if after_first <= before:
        failures.append("a valid claim paid nothing")

    for attempt in range(3):
        try:
            cs.claim_cycle(db, player)
            failures.append(
                f"claim #{attempt + 2} SUCCEEDED -- a stale button pays twice")
            break
        except cs.ChallengeError:
            pass
    if int(player.gold or 0) != after_first:
        failures.append("gold moved on a refused claim")

    # ---- an unplayed cycle offers nothing --------------------------
    fresh = player_service.get_or_create_player(db, 90_002, "NeverPlayed")
    cs.sync_cycle(fresh)
    fresh.challenge_cycle = cs.current_cycle() - 1
    fresh.challenge_points = 0
    fresh.challenge_claimed_cycle = -1
    db.commit()
    points, earned = cs.claimable(fresh)
    if earned:
        failures.append(
            f"a player who scored 0 is offered {[e[1] for e in earned]}")

    # ---- away for several cycles -----------------------------------
    away = player_service.get_or_create_player(db, 90_003, "Away")
    cs.sync_cycle(away)
    away.challenge_cycle = cs.current_cycle() - 4
    away.challenge_points = MILESTONES[0][0]
    away.challenge_claimed_cycle = -1
    db.commit()
    banked, earned = cs.claimable(away)
    if banked != MILESTONES[0][0]:
        failures.append(
            f"a player away 4 cycles banked {banked}, expected "
            f"{MILESTONES[0][0]} -- the week they played was lost")
    if not earned:
        failures.append("a player away 4 cycles earned nothing for a played week")

    # ---- the daily cap really caps points ---------------------------
    capped = player_service.get_or_create_player(db, 90_004, "Grinder")
    cs.sync_cycle(capped)
    capped.challenge_points = 0
    capped.challenges_today = 0
    capped.last_challenge_at = dt.datetime.now(dt.timezone.utc)
    capped.challenge_power = 1000
    db.commit()

    opponent = player_service.get_or_create_player(db, 90_005, "Dummy")
    opponent.challenge_power = 1000
    db.commit()

    fights = REWARDED_CHALLENGES_PER_DAY * 3
    for _ in range(fights):
        cs.resolve(db, capped, opponent, won=True)

    scored = int(capped.challenge_points or 0)
    ceiling = REWARDED_CHALLENGES_PER_DAY * POINTS_PER_WIN * 2  # generous
    if scored > ceiling:
        failures.append(
            f"{fights} fights on a {REWARDED_CHALLENGES_PER_DAY}/day cap "
            f"scored {scored} points (ceiling ~{ceiling}) -- points escape "
            f"the cap the milestones are sized against")

    db.close()

    print(f"cycle       : {cs.current_cycle()}, "
          f"{CYCLE_LENGTH_DAYS}d, ends {cs.cycle_ends_at():%Y-%m-%d %H:%M} UTC")
    print(f"boundaries  : always weekday {weekdays.pop() if len(weekdays) == 1 else '?'}")
    print(f"milestones  : {len(MILESTONES)} rungs, "
          f"{MILESTONES[0][0]}..{MILESTONES[-1][0]} points")
    print(f"cap check   : {fights} wins on a "
          f"{REWARDED_CHALLENGES_PER_DAY}/day cap scored {scored} points")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- cycles roll over on schedule and pay out exactly once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
