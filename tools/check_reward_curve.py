"""
No reward may be richer than the progress needed to reach it.

    python -m tools.check_reward_curve

THE BUG THIS EXISTS FOR
-----------------------
The 'photograph' side mission pays 34,000 gold, 1,700 cores, 1,200
evolution fragments, a mythic item and two mythic lootboxes. It is
Chapter Four material. It sat in the Cascade bunks, two ungated doors
from the Atrium -- so a player who had just finished the PROLOGUE could
walk in and take all of it.

Nothing was wrong with the mission, and nothing was wrong with the
reward. What was wrong was the DOOR, three files away, which had no
`requires_mission` on it. No check in the repo compared the two, because
every existing check looked at one thing at a time: check_story verified
the reward keys were real currencies, check_puzzles verified the puzzle
was solvable, check_progression verified enemy HP rose smoothly. The
reward was valid, the tile was valid, the map was valid, and the
combination handed a new player a mid-game economy.

WHAT THIS CHECKS
----------------
It walks the map the way a player does -- from the spawn, through doors
whose `requires_mission` is satisfied -- once per chapter, accumulating
the missions completed so far. That yields, for every reward in the game,
the EARLIEST point a player can reach it.

Each reward is then compared against a per-chapter budget derived from
what the MAIN STORY pays at that point. The main line is the yardstick
because it is the one thing every player does in order, so it defines
what "on-pace" means. Optional content may pay a multiple of a single
mission's reward -- it should be worth finding -- but not a multiple of
the entire chapter.

Item rarities get the same treatment: a chapter that grants epics should
not have a mythic sitting in an optional room off its corridor.
"""

from __future__ import annotations

import collections
import sys

# How much a single optional reward may pay, as a multiple of the AVERAGE
# per-mission reward of the earliest chapter that can reach it.
#
# 3x is deliberately generous. Optional content that pays the same as a
# required mission is not worth the detour, and the failure mode this
# guards against is not "slightly rich" -- it is the photograph, which
# was paying 34,000 gold in a chapter whose missions pay about 1,700.
MAX_MULTIPLE_OF_CHAPTER_MISSION = 3.0

# Currencies worth policing. Materials are excluded: they are capped by
# their own tier system and a big pile of wood breaks nothing.
TRACKED = ("gold", "cores", "shards", "evolution_fragments", "echoes")

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic",
                "divine"]


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc

    failures: list[str] = []
    chapters = [c["id"] for c in sc.CHAPTERS]
    missions_by_chapter = {c["id"]: [m["id"] for m in c["missions"]]
                           for c in sc.CHAPTERS}

    # ---- what the main story pays, per chapter ----------------------
    # Optional missions are excluded from the yardstick: they are the
    # thing being measured, and letting them set their own budget would
    # make this check unable to fail.
    per_chapter_budget: dict[str, dict] = {}
    for chapter in sc.CHAPTERS:
        required = [m for m in chapter["missions"] if not m.get("optional")]
        totals = collections.Counter()
        best_rarity = -1
        for mission in required:
            for beat in mission.get("beats", []):
                grant = beat.get("grant") or {}
                for key, value in grant.items():
                    if key in TRACKED and isinstance(value, (int, float)):
                        totals[key] += value
                    if key == "item" and isinstance(value, str):
                        best_rarity = max(best_rarity, _rank(value))
                    if key == "lootbox":
                        tier = value[0] if isinstance(value, (list, tuple)) else value
                        best_rarity = max(best_rarity, _rank(tier))
        count = max(1, len(required))
        per_chapter_budget[chapter["id"]] = {
            "per_mission": {k: v / count for k, v in totals.items()},
            "best_rarity": best_rarity,
            "missions": count,
        }

    # ---- earliest reachability, chapter by chapter -------------------
    earliest: dict[tuple, str] = {}   # (area, char) -> chapter id
    completed: set[str] = set()
    for chapter_id in chapters:
        completed |= set(missions_by_chapter[chapter_id])
        for area_id, char in _reachable_tiles(mc, completed):
            earliest.setdefault((area_id, char), chapter_id)

    unreachable = []
    for area_id, area in mc.AREAS.items():
        for char in (area.get("legend") or {}):
            if (area_id, char) not in earliest:
                unreachable.append(f"{area_id}/{char}")

    # ---- compare every reward against its gate -----------------------
    checked = 0
    for (area_id, char), chapter_id in sorted(earliest.items()):
        entry = (mc.AREAS[area_id].get("legend") or {}).get(char) or {}
        budget = per_chapter_budget[chapter_id]

        grants = [entry.get("grant") or {}]

        # A MISSION TILE IS JUDGED BY ITS OWN CHAPTER, and a REQUIRED
        # mission is not judged at all.
        #
        # Two false positives taught this. The prologue's armoury bench
        # pays 600 cores to fund the card pulls it teaches; averaged
        # across the prologue's fourteen missions that reads as an
        # outlier, but a chapter's own required missions ARE the budget
        # and cannot overspend it by definition. And Chapter Three's
        # 'nineteen crates' sits behind a Chapter Two door, so the door's
        # chapter said c2 while the content is c3 -- measured against the
        # wrong yardstick entirely.
        #
        # What this check is actually for is content whose REWARD and
        # whose GATE were decided in different places: optional missions,
        # caches, hunts and puzzles.
        if entry.get("kind") == "mission":
            mission = sc.get_mission(entry.get("mission")) or {}
            owner = _chapter_of(sc, entry.get("mission"))
            if owner and not mission.get("optional"):
                continue
            if owner:
                budget = per_chapter_budget.get(owner, budget)
                chapter_id = owner
            grants += [b.get("grant") or {} for b in mission.get("beats", [])]

        for grant in grants:
            if not grant:
                continue
            checked += 1
            for key, value in grant.items():
                if key in TRACKED and isinstance(value, (int, float)):
                    allowed = (budget["per_mission"].get(key, 0)
                               * MAX_MULTIPLE_OF_CHAPTER_MISSION)
                    # A chapter that pays none of a currency gets a small
                    # absolute allowance, so an early room can still hand
                    # out a first taste of something.
                    allowed = max(allowed, 250 if key != "gold" else 2500)
                    if value > allowed:
                        failures.append(
                            f"{area_id}/{char} is reachable from {chapter_id} and "
                            f"pays {value:,.0f} {key}, but {chapter_id}'s own "
                            f"missions average {budget['per_mission'].get(key, 0):,.0f} "
                            f"-- cap is {allowed:,.0f}")
                if key == "item" and isinstance(value, str):
                    if _rank(value) > budget["best_rarity"]:
                        failures.append(
                            f"{area_id}/{char} is reachable from {chapter_id} and "
                            f"grants a {value} item, but that chapter's best is "
                            f"{RARITY_ORDER[budget['best_rarity']] if budget['best_rarity'] >= 0 else 'nothing'}")
                if key == "lootbox":
                    tier = value[0] if isinstance(value, (list, tuple)) else value
                    if _rank(tier) > budget["best_rarity"]:
                        failures.append(
                            f"{area_id}/{char} is reachable from {chapter_id} and "
                            f"grants a {tier} lootbox, above that chapter's best")

    print(f"tiles      : {len(earliest)} reachable, {checked} reward blocks checked")
    for chapter_id in chapters:
        opened = sum(1 for c in earliest.values() if c == chapter_id)
        b = per_chapter_budget[chapter_id]
        print(f"  {chapter_id:<10} opens {opened:>3} tiles · per-mission "
              f"{b['per_mission'].get('gold', 0):>7,.0f} gold · best item "
              f"{RARITY_ORDER[b['best_rarity']] if b['best_rarity'] >= 0 else '-'}")
    if unreachable:
        print(f"unreachable: {len(unreachable)} tile(s) no gate ever opens "
              f"({', '.join(unreachable[:6])})")

    if failures:
        print()
        for failure in sorted(set(failures)):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every reward is in proportion to the progress that reaches it.")
    return 0


def _chapter_of(sc, mission_id: str | None) -> str | None:
    for chapter in sc.CHAPTERS:
        if any(m["id"] == mission_id for m in chapter["missions"]):
            return chapter["id"]
    return None


def _rank(rarity: str) -> int:
    try:
        return RARITY_ORDER.index(str(rarity).lower())
    except ValueError:
        return -1


def _reachable_tiles(mc, completed: set[str]):
    """Every (area, char) a player with `completed` missions can stand on
    and use -- doors and tiles both respect requires_mission."""
    def open_(entry):
        required = entry.get("requires_mission")
        return not required or required in completed

    reached = {mc.STARTING_AREA}
    frontier = [mc.STARTING_AREA]
    while frontier:
        area_id = frontier.pop()
        for entry in (mc.AREAS[area_id].get("legend") or {}).values():
            if entry.get("kind") == "exit" and open_(entry):
                target = entry.get("to_area")
                if target in mc.AREAS and target not in reached:
                    reached.add(target)
                    frontier.append(target)

    for area_id in reached:
        for char, entry in (mc.AREAS[area_id].get("legend") or {}).items():
            if open_(entry):
                yield area_id, char


if __name__ == "__main__":
    raise SystemExit(main())
