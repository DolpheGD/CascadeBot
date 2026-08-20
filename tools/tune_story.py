"""
Solve for the enemy level of every story battle.

    python -m tools.tune_story            # report only
    python -m tools.tune_story --write     # rewrite story_config levels

WHY THIS IS A TOOL AND NOT A ONE-OFF SCRIPT
-------------------------------------------
The story's 28 battle levels have now been tuned twice against a model
that was wrong, and both times the numbers looked plausible in the diff.
The second time, enemy levels ended up in the 30s for a chapter the
player reaches at level 14 -- more than double the player's level -- and
nothing in the source made that visibly absurd, because a level is just
an integer next to a list of enemy names.

So the levels are no longer authored. They are SOLVED, here, against
tools.check_story's difficulty model, and this file records the target
curve that produced them. If the model changes again, re-run this rather
than hand-editing, and the two will not drift apart.

TWO NUMBERS, BECAUSE NEITHER ONE WORKS ALONE
--------------------------------------------
This was solved against health cost, then against win rate, and both
single-metric versions produced a story that passed its own check and was
still wrong.

HEALTH COST ALONE fails at the hard end. Chapter Two's climax had the
highest health cost in its chapter (47%) and a 96% win rate -- a fight
the party comfortably wins still spends health winning it -- while
Chapter Four's climax read 73% cost and was a 50% coin flip. Cost cannot
tell "long grind you win" apart from "fight you lose", and those are not
remotely the same experience.

WIN RATE ALONE fails at the easy end, because it saturates. Everything
comfortable reads 100%, so there is no gradient left to solve against:
asked for a 95% opener, the solver dropped Chapter One's first fight to a
level where it cost 6% of the squad's health -- exactly on target, and a
complete anticlimax after a prologue that ended at 10%.

So the solve targets health COST, which has a usable gradient across the
whole range, subject to a WIN-RATE FLOOR, which is the fairness
guarantee. check_story asserts both separately. A fight is right when it
costs about what its position in the story says it should AND the player
still wins it comfortably more often than not.

THE RAMP, from the same sentence in the brief ("fair, and helps power up
the player to face Rohan at the end"):

  * WITHIN a chapter, cost climbs and the chapter ends on its hardest
    fight.
  * ACROSS chapters, each climax costs more than the last, so the story
    is one continuous ramp to Rohan rather than five difficulty islands.

The climax targets stop at 68 rather than climbing to 78. Past roughly
that point the only way to buy more cost is more lethality, and every
level that pushed cost higher pushed the win rate under the floor -- 78%
cost was reachable, at a 38% win rate.
"""

from __future__ import annotations

import argparse
import re
import sys

# Health-cost target per fight, by position within the chapter. The last
# entry of each row is the chapter climax, and each row's climax is above
# the previous row's -- that ordering IS the ramp, and check_story
# asserts it.
TARGETS: dict[str, list[int]] = {
    "chapter1": [14, 20, 26, 32],
    "chapter2": [20, 26, 32, 38],
    "chapter3": [26, 32, 38, 43],
    "chapter4": [32, 38, 43, 48],
    "chapter5": [36, 42, 47, 53],
}

# THE LADDER IS SCALED TO A CEILING IT DID NOT CHOOSE.
#
# The first version of this table climbed to 78 for the finale, and 78
# was reachable -- at a 38% win rate. Sweeping the final boss across
# 2-4 actions per cycle, elemental 7-24 and HP 900-3400 found no
# configuration at all that cost a squad more than about 52% of its
# health while still being won 65% of the time.
#
# That ceiling is a property of the combat system rather than of any one
# fight: a party with a working healer either stabilises (and then a
# longer fight costs no more health, just more turns) or it does not (and
# then it loses). There is no "grindingly expensive but reliably won"
# region to tune into. So the whole ladder sits underneath the ceiling
# and spends its range on ORDERING, which is the part players actually
# perceive, rather than on absolute numbers that cannot be delivered.

# No fight is allowed to sit below this win rate against a squad at the
# level the story's own XP grants produce, whatever the cost target says.
# The story is the one part of the game everybody has to get through, so
# a fight the player loses as often as they win is a wall rather than a
# difficulty curve -- and four of them passed review before this floor
# existed, including a 50% coin flip as the climax of Chapter Four.
WIN_FLOOR = 65.0

# Enemy LEVEL is a coarse dial -- one level of Rohan's Negadom can move a
# fight several points -- so a target that falls between two levels is
# resolved to the nearer one and the solver reports the miss rather than
# pretending. That is also why the rows step by 6-8 points instead of 1:
# a gap smaller than the simulator's own noise is not a difficulty
# difference, it is a rounding artefact, and asking the solver to hit one
# produces levels that reshuffle on every re-run.

# The prologue is deliberately absent. It is measured against a party
# that GROWS mission by mission (see check_story._roster_before), so its
# fights are not comparable to the four-character chapters, and at 0-10%
# it is already doing its job -- teaching, not testing.

LEVEL_MIN, LEVEL_MAX = 1, 90


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="rewrite story_config.py with the solved levels")
    parser.add_argument("--seeds", type=int, default=24,
                        help="battles per measurement during the coarse bisection "
                             "(the refinement pass always re-measures at check_story's "
                             "own seed count, so solver and checker cannot disagree)")
    parser.add_argument("--tolerance", type=float, default=6.0,
                        help="stop when within this many points of the target "
                             "health cost (chasing a tighter fit than the "
                             "measurement supports just reshuffles levels "
                             "between runs)")
    args = parser.parse_args()

    sys.path.insert(0, ".")
    from bot.game.story import story_config as sc
    from tools.check_story import build_difficulty_model

    model = build_difficulty_model()
    simulate = model["simulate"]
    level_from_xp = model["level_from_story_xp"]
    verify_seeds = model["default_seeds"]

    solved: list[tuple[str, str, int, int, float]] = []

    for chapter in sc.CHAPTERS:
        targets = TARGETS.get(chapter["id"])
        if not targets:
            continue
        squad_level = level_from_xp(chapter["id"])
        fights = [
            (mission["name"], beat)
            for mission in chapter["missions"]
            for beat in mission.get("beats", [])
            if beat.get("kind") == "battle"
        ]
        print(f"\n{chapter['name']}  (squad level {squad_level})")
        for index, (name, beat) in enumerate(fights):
            target = targets[min(index, len(targets) - 1)]
            enemies = beat["enemies"]

            # BISECTION, not hill-climbing from the current value.
            # Health cost rises monotonically with enemy level, so
            # bisection is both correct and bounded; stepping from the
            # current level meant the previous tuner could walk uphill
            # for twenty iterations and stop somewhere arbitrary.
            low, high = LEVEL_MIN, LEVEL_MAX
            best_level = beat.get("level", 1)
            best_cost, best_win, best_gap = 100.0, 0.0, 1e9
            for _ in range(8):
                mid = (low + high) // 2
                measured, win = simulate(enemies, mid, squad_level,
                                         seeds=args.seeds,
                                         chapter_id=chapter["id"])
                gap = abs(measured - target)
                if gap < best_gap:
                    best_level, best_cost, best_win = mid, measured, win * 100
                    best_gap = gap
                if best_gap <= args.tolerance:
                    break
                if measured < target:
                    low = mid + 1
                else:
                    high = mid - 1
                if low > high:
                    break

            # REFINEMENT AT THE CHECKER'S OWN SEED COUNT.
            #
            # The bisection above runs cheap so it can afford eight
            # probes; cheap measurements drift by several points (see the
            # convergence table in check_story). Without this pass the
            # tuner solved a fight to 59% and check_story then measured
            # the SAME fight at 66% -- the solver and the checker were
            # looking at different numbers, which is the whole bug this
            # file exists to prevent, reintroduced one layer down.
            candidates = {}
            for level in (best_level - 1, best_level, best_level + 1):
                if LEVEL_MIN <= level <= LEVEL_MAX:
                    candidates[level] = simulate(enemies, level, squad_level,
                                                 seeds=verify_seeds,
                                                 chapter_id=chapter["id"])
            if candidates:
                best_level = min(candidates,
                                 key=lambda lv: abs(candidates[lv][0] - target))
                best_cost, win = candidates[best_level]
                best_win = win * 100
                best_gap = abs(best_cost - target)

            # THE FAIRNESS FLOOR OVERRIDES THE COST TARGET.
            #
            # Cost and lethality are not independent -- past a point the
            # only way to make a fight cost more is to make it kill more
            # -- so a cost target can be satisfied by a fight the player
            # loses. When that happens the cost target is simply wrong for
            # this matchup, and the level walks DOWN until the fight is
            # winnable again. Better an easy chapter than an unfair one.
            floor_steps = 0
            while best_win < WIN_FLOOR and best_level > LEVEL_MIN:
                best_level -= 1
                floor_steps += 1
                best_cost, win = simulate(enemies, best_level, squad_level,
                                          seeds=verify_seeds,
                                          chapter_id=chapter["id"])
                best_win = win * 100
                best_gap = abs(best_cost - target)
                if floor_steps > 25:
                    break

            was = beat.get("level", 1)
            if best_win < WIN_FLOOR:
                flag = "  (UNFAIR: below the win floor at every level)"
            elif floor_steps:
                flag = f"  (held back {floor_steps} levels by the win floor)"
            elif best_gap > args.tolerance:
                flag = "  (could not hit target)"
            else:
                flag = ""
            print(f"  {name[:30]:<32} lvl {was:>3} -> {best_level:>3}   "
                  f"costs {best_cost:>3.0f}% (target {target}%)  "
                  f"won {best_win:>3.0f}%{flag}")
            solved.append((chapter["id"], name, was, best_level, best_win))

    if args.write:
        _write(solved)
        print(f"\nwrote {len(solved)} levels into story_config.py")
    else:
        print("\n(report only -- pass --write to apply)")
    return 0


def _write(solved: list[tuple[str, str, int, int, float]]) -> None:
    """Rewrite the `"level": N` of each battle beat in place.

    Edits the SOURCE rather than emitting a table to paste, because a
    table to paste is a second place the numbers live and this file
    exists specifically to stop that happening again.
    """
    path = "bot/game/story/story_config.py"
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    # Battle beats are the only blocks with both "enemies" and "level",
    # so anchoring on that pair cannot hit a mission's own level field.
    pattern = re.compile(
        r'("kind":\s*"battle".*?"level":\s*)(\d+)', re.DOTALL)

    levels = [new for _, _, _, new, _ in solved]
    index = 0
    prologue_count = _count_prologue_battles()

    def replace(match):
        nonlocal index
        # The prologue's battles come first in the file and are not
        # tuned; skip exactly that many before consuming solved levels.
        current, index = index, index + 1
        if current < prologue_count:
            return match.group(0)
        position = current - prologue_count
        if position >= len(levels):
            return match.group(0)
        return f"{match.group(1)}{levels[position]}"

    text = pattern.sub(replace, text)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _count_prologue_battles() -> int:
    from bot.game.story import story_config as sc
    prologue = next((c for c in sc.CHAPTERS if c["id"] == "prologue"), None)
    return sum(
        1
        for mission in (prologue or {}).get("missions", [])
        for beat in mission.get("beats", [])
        if beat.get("kind") == "battle"
    )


if __name__ == "__main__":
    raise SystemExit(main())
