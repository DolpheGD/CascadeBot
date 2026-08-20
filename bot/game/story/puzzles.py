"""
Puzzle definitions and solvers for story mode.

Four kinds, all of them resolved by pure functions in this module so they
can be exercised without a database, a Discord interaction or a player --
see tools/check_puzzles.py, which brute-forces every authored puzzle
against its own solver.

WHY THE SOLVER LIVES HERE AND NOT IN THE COG
--------------------------------------------
The obvious place to check "did they get it right" is next to the button
that submits the answer. That is also the place where nothing can ever be
tested: it needs an Interaction, a live view and a session. Every puzzle
would then be verified exactly once, by hand, by whoever wrote it.

So the cog owns presentation and this module owns truth. `solve()` takes
a puzzle dict and a submission and returns a verdict. That is the whole
interface, and it means a puzzle whose answer is unreachable fails in the
check suite rather than in front of a player twenty minutes into a
chapter.

THE FOUR KINDS
--------------
"code"      Deduction. Clues are scattered across the area's note tiles;
            the player works out a code/name/number and enters it. The
            answer is a string, compared case- and space-insensitively,
            because "SURVEY 9" and "survey9" are the same answer and
            failing one of them is a bug, not a difficulty setting.

"sequence"  Ordering. The player presses N labelled buttons in the right
            order. Submission is the list of step ids in press order.

"logic"     A constraint grid: assign each subject exactly one value
            (five teams, five camps) consistent with the stated clues.
            Submission is a {subject: value} mapping.

"wiring"    Connect labelled terminals in pairs. Submission is a list of
            [a, b] pairs; order within a pair and order of pairs are both
            irrelevant, which is what a player would expect and is easy
            to get wrong.

EVERY PUZZLE CAN BE SKIPPED
---------------------------
`optional` defaults to True and the story engine honours it. A puzzle
that gates story progress is a puzzle that can strand somebody who does
not enjoy puzzles inside a narrative they were enjoying. The rewards are
the incentive; the wall is not. The two puzzles that ARE required
(marked optional=False) sit on optional map tiles, so the thing they gate
is itself skippable.
"""

from __future__ import annotations

PUZZLE_KINDS = ("code", "sequence", "logic", "wiring")


def _normalise(text: str) -> str:
    """Casefold, strip, and drop internal whitespace and separators.

    Deliberately aggressive. A player who deduces the answer "SP-9" and
    types "sp 9" has solved the puzzle, and a checker that says otherwise
    is testing typing rather than deduction.
    """
    return "".join(ch for ch in str(text).casefold() if ch.isalnum())


def kind_of(puzzle: dict) -> str:
    """Which of the four kinds this puzzle is.

    Read from `puzzle_kind`, NOT `kind`. Both a map tile and a story beat
    already use `kind` for what they are ("puzzle"), so a puzzle that
    stored its type there would be overwriting the field the map and the
    beat engine dispatch on. The first authored puzzle did exactly that
    and reported itself as kind 'puzzle', which is not one of the four.
    """
    return puzzle.get("puzzle_kind") or ""


def solve(puzzle: dict, submission) -> tuple[bool, str]:
    """(solved, message). Never raises on bad input -- a malformed
    submission is a wrong answer, not a crash, because the submission
    ultimately comes from a Discord modal the player can type anything
    into."""
    kind = kind_of(puzzle)
    if kind == "code":
        return _solve_code(puzzle, submission)
    if kind == "sequence":
        return _solve_sequence(puzzle, submission)
    if kind == "logic":
        return _solve_logic(puzzle, submission)
    if kind == "wiring":
        return _solve_wiring(puzzle, submission)
    return False, "That puzzle is broken. Nothing you did caused it."


def _solve_code(puzzle: dict, submission) -> tuple[bool, str]:
    # `answers` rather than `answer`: several puzzles have more than one
    # defensible phrasing of the same deduction ("nineteen" / "19"), and
    # accepting only the author's favourite is a way of being wrong at
    # the player.
    accepted = puzzle.get("answers") or [puzzle.get("answer", "")]
    wanted = {_normalise(a) for a in accepted}
    if _normalise(submission) in wanted:
        return True, puzzle.get("on_solve", "It opens.")
    return False, puzzle.get("on_fail", "Nothing happens.")


def _solve_sequence(puzzle: dict, submission) -> tuple[bool, str]:
    order = list(puzzle.get("order") or [])
    try:
        given = [str(s) for s in submission]
    except TypeError:
        return False, puzzle.get("on_fail", "Nothing happens.")
    if given == order:
        return True, puzzle.get("on_solve", "It runs.")
    return False, puzzle.get("on_fail", "It stops, and resets itself.")


def _solve_logic(puzzle: dict, submission) -> tuple[bool, str]:
    solution = dict(puzzle.get("solution") or {})
    if not isinstance(submission, dict):
        return False, puzzle.get("on_fail", "That doesn't hold together.")
    if {k: str(v) for k, v in submission.items()} == {k: str(v) for k, v in solution.items()}:
        return True, puzzle.get("on_solve", "Every line agrees.")
    return False, puzzle.get("on_fail", "Two of those contradict each other.")


def _solve_wiring(puzzle: dict, submission) -> tuple[bool, str]:
    # Pairs are UNORDERED, both within a pair and between pairs. Encoding
    # them as a set of frozensets is the cheap way to say that once,
    # rather than sorting in four places and forgetting one.
    def canonical(pairs):
        out = set()
        for pair in pairs:
            a, b = list(pair)[:2]
            out.add(frozenset((str(a), str(b))))
        return out

    try:
        given = canonical(submission)
    except (TypeError, ValueError):
        return False, puzzle.get("on_fail", "That shorts out.")
    if given == canonical(puzzle.get("pairs") or []):
        return True, puzzle.get("on_solve", "Everything lights.")
    return False, puzzle.get("on_fail", "Something shorts, and the board resets.")


def describe(puzzle: dict) -> str:
    """The prompt text, plus whatever the player needs on screen to
    actually attempt it. Kept here rather than in the cog so the check
    suite can assert a puzzle is presentable without building an embed."""
    parts = [puzzle.get("text", "")]
    if kind_of(puzzle) == "logic":
        subjects = ", ".join(puzzle.get("subjects") or [])
        values = ", ".join(puzzle.get("values") or [])
        parts.append(f"\n**Assign each of:** {subjects}\n**One of:** {values}")
    if puzzle.get("clues"):
        parts.append("\n" + "\n".join(f"• {clue}" for clue in puzzle["clues"]))
    return "\n".join(p for p in parts if p)
