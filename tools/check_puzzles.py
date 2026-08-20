"""
Validate every puzzle in the game.

    python -m tools.check_puzzles

A puzzle is the one kind of content where "it looked right in the source"
is worth nothing. A note with a typo is a typo. A puzzle with a typo is a
player entering the correct answer, being told they are wrong, and having
no way to tell whether they misunderstood the clues or the game is
broken. They will assume they misunderstood, and they will keep trying.

So every puzzle is actually SOLVED here, by calling the real solver in
bot/game/story/puzzles.py with the authored solution:

  1. THE ANSWER IS ACCEPTED. `solve(puzzle, its own solution)` must
     return True. This catches the whole family of bugs where the answer
     key and the checker disagree -- a sequence listed in display order
     but compared in press order, a wiring pair written [a, b] and
     compared as [b, a].

  2. WRONG ANSWERS ARE REJECTED. A solver that returns True for
     everything passes test 1 perfectly. Each puzzle is therefore also
     fed a deliberately wrong submission, and must reject it.

  3. THE ANSWER IS DERIVABLE. For `code` puzzles the answer has to be
     reachable from clues the player can actually read -- either the
     puzzle's own `clues` list or the text of note tiles in the SAME
     area. A code puzzle whose answer appears nowhere is a guessing game.

  4. NOTHING SOFT-LOCKS. A puzzle beat inside a mission must be skippable
     (`optional`), or the mission must be optional itself. Otherwise a
     player who cannot solve it cannot finish the story.

  5. PRESENTABILITY. Every puzzle renders a non-empty prompt, has a
     reward, and -- for the interactive kinds -- has few enough elements
     to fit Discord's 25-option / 5-row limits.
"""

from __future__ import annotations

import sys


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc
    from bot.game.story.puzzles import PUZZLE_KINDS, describe, kind_of, solve
    from bot.services.currency_service import VALID_CURRENCIES

    failures: list[str] = []
    puzzles: list[tuple[str, dict, str | None]] = []

    # Map-tile puzzles, with the area they live in (for clue derivation).
    for area_id, area in mc.AREAS.items():
        for char, entry in (area.get("legend") or {}).items():
            if entry.get("kind") == "puzzle":
                puzzles.append((f"{area_id}/{char}", entry, area_id))

    # Beat puzzles inside missions.
    for mission in sc.all_missions():
        for index, beat in enumerate(mission.get("beats", [])):
            if beat.get("kind") == "puzzle":
                puzzles.append((f"{mission['id']} beat {index}", beat, None))
                if not beat.get("optional", True) and not mission.get("optional"):
                    failures.append(
                        f"{mission['id']} beat {index}: a REQUIRED puzzle inside a "
                        f"REQUIRED mission -- a player who cannot solve it can never "
                        f"finish the story"
                    )

    if not puzzles:
        print("no puzzles defined")
        return 0

    for where, puzzle, area_id in puzzles:
        kind = kind_of(puzzle)
        if kind not in PUZZLE_KINDS:
            failures.append(f"{where}: unknown puzzle kind {kind!r}")
            continue

        if not describe(puzzle).strip():
            failures.append(f"{where}: renders an empty prompt")
        if not puzzle.get("grant"):
            failures.append(
                f"{where}: no reward -- a puzzle that pays nothing is homework")
        for currency, amount in (puzzle.get("grant") or {}).items():
            if currency in ("item", "lootbox", "xp"):
                continue
            if currency not in VALID_CURRENCIES:
                failures.append(f"{where}: reward currency {currency!r} does not exist")

        # ---- 1 & 2: the solver agrees with the answer key, and only
        # with the answer key.
        correct, wrong = _submissions(puzzle)
        if correct is None:
            failures.append(f"{where}: has no authored solution to check against")
            continue

        ok, _message = solve(puzzle, correct)
        if not ok:
            failures.append(
                f"{where}: the authored solution is REJECTED by its own solver -- "
                f"a player who works this out correctly would be told they are wrong"
            )
        for bad in wrong:
            bad_ok, _ = solve(puzzle, bad)
            if bad_ok:
                failures.append(
                    f"{where}: accepts the wrong submission {bad!r} -- this puzzle "
                    f"cannot be failed, so it is not a puzzle"
                )

        # ---- 3: a code answer must appear in the clues the player has.
        if kind == "code":
            failures.extend(_check_derivable(where, puzzle, area_id, mc))

        # ---- 5: Discord limits on the interactive kinds.
        if kind == "sequence" and len(puzzle.get("order") or []) > 20:
            failures.append(f"{where}: {len(puzzle['order'])} steps (keep under 20)")
        if kind == "logic":
            subjects = puzzle.get("subjects") or []
            values = puzzle.get("values") or []
            if len(subjects) != len(values):
                failures.append(
                    f"{where}: {len(subjects)} subjects but {len(values)} values -- "
                    f"a one-to-one assignment needs the same count of each")
            if set((puzzle.get("solution") or {})) != set(subjects):
                failures.append(f"{where}: solution does not cover exactly the subjects")
            if sorted(str(v) for v in (puzzle.get("solution") or {}).values()) != \
                    sorted(str(v) for v in values):
                failures.append(
                    f"{where}: solution reuses or omits a value -- it is not a "
                    f"one-to-one assignment")
            if len(subjects) > 25:
                failures.append(f"{where}: {len(subjects)} subjects exceeds a select")
        if kind == "wiring":
            pairs = puzzle.get("pairs") or []
            flat = [str(t) for pair in pairs for t in pair]
            if len(flat) != len(set(flat)):
                failures.append(
                    f"{where}: a terminal appears in two pairs -- ambiguous solution")
            if len(pairs) > 12:
                failures.append(f"{where}: {len(pairs)} pairs is too many buttons")

    by_kind: dict[str, int] = {}
    for _where, puzzle, _area in puzzles:
        by_kind[kind_of(puzzle) or "?"] = by_kind.get(kind_of(puzzle) or "?", 0) + 1
    print(f"puzzles  : {len(puzzles)} "
          f"({', '.join(f'{n} {k}' for k, n in sorted(by_kind.items()))})")
    optional = sum(1 for _w, p, _a in puzzles if p.get("optional", True))
    print(f"optional : {optional}/{len(puzzles)} can be walked away from")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every puzzle is solvable, failable, and derivable from its clues.")
    return 0


def _submissions(puzzle: dict):
    """(a correct submission, [some wrong ones]) for this puzzle kind."""
    from bot.game.story.puzzles import kind_of
    kind = kind_of(puzzle)
    if kind == "code":
        accepted = puzzle.get("answers") or ([puzzle["answer"]] if puzzle.get("answer") else [])
        if not accepted:
            return None, []
        return accepted[0], ["definitely-not-the-answer", ""]
    if kind == "sequence":
        order = list(puzzle.get("order") or [])
        if not order:
            return None, []
        wrong = [list(reversed(order))] if len(order) > 1 else []
        wrong.append(order[:-1])          # right prefix, short
        return order, wrong
    if kind == "logic":
        solution = dict(puzzle.get("solution") or {})
        if not solution:
            return None, []
        keys = list(solution)
        swapped = dict(solution)
        if len(keys) > 1:
            swapped[keys[0]], swapped[keys[1]] = solution[keys[1]], solution[keys[0]]
        return solution, ([swapped] if len(keys) > 1 else []) + [{}]
    if kind == "wiring":
        pairs = [list(p) for p in (puzzle.get("pairs") or [])]
        if not pairs:
            return None, []
        wrong = []
        if len(pairs) > 1:
            crossed = [p[:] for p in pairs]
            crossed[0][1], crossed[1][1] = crossed[1][1], crossed[0][1]
            wrong.append(crossed)
        wrong.append(pairs[:-1])
        return pairs, wrong
    return None, []


def _check_derivable(where: str, puzzle: dict, area_id: str | None, mc) -> list[str]:
    """A code answer must appear in text the player can read.

    Searched: the puzzle's own clues and text, and every note/cache tile
    in the same area. Matching is done on the same normalisation the
    solver uses, so "Survey 9" in a note satisfies an answer of "sp9"
    only if the author also listed that spelling -- which is the correct
    strictness, because the player has to type something the solver
    accepts.
    """
    from bot.game.story.puzzles import _normalise

    accepted = puzzle.get("answers") or [puzzle.get("answer", "")]
    haystack = " ".join(
        [puzzle.get("text", "")] + list(puzzle.get("clues") or []))
    if area_id:
        area = mc.AREAS.get(area_id) or {}
        for entry in (area.get("legend") or {}).values():
            if entry.get("kind") in ("note", "cache", "npc", "puzzle"):
                haystack += " " + str(entry.get("text", ""))
                for line in entry.get("lines") or []:
                    haystack += " " + str(line.get("text", ""))

    normalised = _normalise(haystack)
    if any(_normalise(a) and _normalise(a) in normalised for a in accepted):
        return []
    # `derivation` is the escape hatch for answers that are computed
    # rather than quoted -- "add the three team numbers" is derivable
    # without the digits ever appearing as a string. Requiring the author
    # to write down HOW it is derived keeps the check honest instead of
    # just switchable-off.
    if puzzle.get("derivation"):
        return []
    return [
        f"{where}: none of its accepted answers appear in the clues or in any note "
        f"in {area_id or 'the mission'} -- the player would be guessing. Add a clue, "
        f"or a `derivation` note explaining how it is worked out."
    ]


if __name__ == "__main__":
    raise SystemExit(main())
