"""
Validate the commission system.

    python -m tools.check_commissions

Commissions are the third quest kind and they fail QUIETLY in three
different ways, all of which look identical to a working commission from
the outside: the contract appears on the board, the player takes it, and
then nothing ever happens. Each one is checked here.

  1. A GOAL NOBODY REPORTS. quest_service.record_progress matches
     goal_type as an exact string. A commission asking for
     "defeat_elite@The Hotlads" -- one letter wrong -- sits at 0/4
     forever. So every goal type is checked against the set of types the
     bot actually reports, and every region-scoped goal against both
     quest_config.REGION_SCOPED_GOALS and the real region list.

  2. A REWARD NOBODY CAN LOOK UP. record_progress finds a finished
     quest's reward via _quest_config_by_id, which searches a hardcoded
     tuple of pools. A pool missing from that tuple produces quests that
     complete and pay nothing. Every id in every pool is resolved through
     the real function here.

  3. A CONTRACT NOBODY CAN REACH. `requires_mission` naming a mission
     that does not exist means the contract never appears on the board at
     all, and an empty board looks like a board with nothing new on it.

Also checked: reward currencies are real, ids are unique across ALL three
pools (they share one table and one lookup, so a collision between a
commission and a basic quest would resolve to whichever pool is searched
first), and the board tile is actually placed on a map somewhere.
"""

from __future__ import annotations

import sys


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.dungeon.region_config import ordered_regions
    from bot.game.economy.quest_config import (
        BASIC_QUEST_POOL,
        BEGINNER_QUESTS,
        COMMISSIONS,
        MAX_ACTIVE_COMMISSIONS,
        REGION_SCOPED_GOALS,
    )
    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc
    from bot.services.currency_service import VALID_CURRENCIES
    from bot.services.quest_service import _quest_config_by_id

    failures: list[str] = []

    # The goal types the bot genuinely reports progress against. Derived
    # from the call sites listed in quest_service's module docstring; kept
    # here as an explicit list so that ADDING a goal type to a config
    # without adding a record_progress call fails loudly.
    REPORTED_GOALS = {
        "win_battles", "defeat_boss", "defeat_elite", "complete_adventures",
        "upgrade_gear", "claim_daily", "gacha_pulls", "buy_harvester",
        "collect_harvester", "open_lootboxes", "vote", "reach_floor",
        "hq_level",
    }
    regions = set(ordered_regions())
    mission_ids = {m["id"] for m in sc.all_missions()}

    # ---- 1. goal types resolve to something that is actually reported --
    for commission in COMMISSIONS:
        goal = commission["goal_type"]
        where = f"commission '{commission['id']}'"
        if "@" in goal:
            base, _, region = goal.partition("@")
            if base not in REGION_SCOPED_GOALS:
                failures.append(
                    f"{where}: goal '{base}' is scoped to a region, but only "
                    f"{sorted(REGION_SCOPED_GOALS)} are reported in region-qualified "
                    f"form -- this commission would never advance"
                )
            if region not in regions:
                failures.append(
                    f"{where}: region {region!r} does not exist "
                    f"(have: {', '.join(sorted(regions))})"
                )
        elif goal not in REPORTED_GOALS:
            failures.append(
                f"{where}: goal type {goal!r} is never reported by any "
                f"record_progress call -- this commission would never advance"
            )

        if not isinstance(commission.get("goal_count"), int) or commission["goal_count"] < 1:
            failures.append(f"{where}: goal_count must be a positive int")

        for key in ("name", "giver", "description"):
            if not str(commission.get(key, "")).strip():
                failures.append(f"{where}: missing {key}")

        required = commission.get("requires_mission")
        if required and required not in mission_ids:
            failures.append(
                f"{where}: requires_mission {required!r} is not a real mission -- "
                f"this contract can never appear on the board"
            )

        for currency, amount in (commission.get("reward") or {}).items():
            if currency not in VALID_CURRENCIES:
                failures.append(f"{where}: reward currency {currency!r} does not exist")
            if not isinstance(amount, int) or amount <= 0:
                failures.append(f"{where}: reward {currency} must be a positive int")

    # ---- 2. every id in every pool resolves through the real lookup ----
    #
    # Calling the actual private function rather than reimplementing the
    # search. A check that reimplements the thing it is checking passes
    # when the real code is broken, which is how four earlier checks in
    # this repo missed the exact bug they were written for.
    for pool_name, pool in (("BEGINNER_QUESTS", BEGINNER_QUESTS),
                            ("BASIC_QUEST_POOL", BASIC_QUEST_POOL),
                            ("COMMISSIONS", COMMISSIONS)):
        for entry in pool:
            if _quest_config_by_id(entry["id"]) is None:
                failures.append(
                    f"{pool_name} entry {entry['id']!r} is not findable by "
                    f"quest_service._quest_config_by_id -- it would complete and "
                    f"pay out nothing at all"
                )

    # ---- 3. ids unique across all three pools ----
    seen: dict[str, str] = {}
    for pool_name, pool in (("BEGINNER_QUESTS", BEGINNER_QUESTS),
                            ("BASIC_QUEST_POOL", BASIC_QUEST_POOL),
                            ("COMMISSIONS", COMMISSIONS)):
        for entry in pool:
            if entry["id"] in seen:
                failures.append(
                    f"id {entry['id']!r} is in both {seen[entry['id']]} and "
                    f"{pool_name} -- they share one table and one lookup"
                )
            seen[entry["id"]] = pool_name

    # ---- 4. the board exists on a map ----
    boards = [
        (area_id, char)
        for area_id, area in mc.AREAS.items()
        for char, entry in (area.get("legend") or {}).items()
        if entry.get("kind") == "board"
    ]
    if not boards:
        failures.append(
            "no area has a 'board' tile -- every commission is unreachable"
        )

    # ---- 5. the board is reachable before the contracts on it ----
    #
    # A board gated behind Chapter Four holding Chapter One contracts is
    # not obviously wrong in the source and is completely useless in play.
    earliest = None
    order = [m["id"] for m in sc.all_missions()]
    for commission in COMMISSIONS:
        required = commission.get("requires_mission")
        if required in order:
            position = order.index(required)
            if earliest is None or position < earliest:
                earliest = position
    for area_id, char in boards:
        gate = (mc.AREAS[area_id]["legend"][char]).get("requires_mission")
        if gate and gate in order and earliest is not None and order.index(gate) > earliest:
            failures.append(
                f"the board in '{area_id}' is gated behind '{gate}', which comes "
                f"after the earliest contract's own gate -- those contracts would "
                f"be unreachable when they unlock"
            )

    print(f"commissions : {len(COMMISSIONS)} "
          f"({sum(1 for c in COMMISSIONS if c.get('repeatable'))} repeatable), "
          f"{MAX_ACTIVE_COMMISSIONS} held at once")
    scoped = [c for c in COMMISSIONS if "@" in c["goal_type"]]
    print(f"region-scoped: {len(scoped)} of them, across "
          f"{len({c['goal_type'].partition('@')[2] for c in scoped})} regions")
    print(f"boards      : {len(boards)} placed "
          f"({', '.join(a for a, _ in boards) or 'none'})")
    total = sum(sum((c.get('reward') or {}).values()) for c in COMMISSIONS)
    print(f"payout      : {total:,} units of currency across every contract")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every commission is reachable, advanceable and payable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
