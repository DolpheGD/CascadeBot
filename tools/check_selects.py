"""
Catch select menus whose default option cannot be chosen.

    python -m tools.check_selects

THE BUG THIS EXISTS FOR
-----------------------
Reported as "I can't fight standard on raids". Every other raid
difficulty worked. Standard did nothing at all.

Standard is DEFAULT_RAID_DIFFICULTY, and the difficulty picker marked it
`default=True`. A Discord select treats a default option as ALREADY
SELECTED -- and selecting the value that is already selected dispatches
NO interaction. So the option most players wanted was the one option
where clicking was a no-op, and it looked like a Standard problem rather
than a select problem.

THE DISTINCTION THAT MATTERS
----------------------------
`default=` is not wrong in general. There are two kinds of select and it
is correct on exactly one of them:

  * A STATE select shows what is currently true and switches it -- the
    combat target, the profile's character, the /help page, the sort
    order. Marking the current value is right, and re-picking it being
    inert is also right, because choosing what is already chosen changes
    nothing. Eleven selects in this codebase are this kind.

  * An ACTION select performs something with the value picked -- attack
    at this difficulty, buy this character, use this ability. Here a
    default is a trap: it pre-selects a value the player never chose,
    and then silently refuses to let them choose it.

The two are told apart by what the callback DOES, which no static rule
can read perfectly. So this checker asks a narrower, decidable question:
does the option marked default come from a CONSTANT (a configured
default, i.e. an action select pre-filling a suggestion) rather than
from the view's own current state (a state select reflecting itself)?

A default compared against something named `current`, `selected`,
`self.page`, `battle.target_index` and so on is state. A default
compared against a module-level DEFAULT_* constant is the raid bug.
"""

from __future__ import annotations

import ast
import pathlib
import sys

# Names that indicate the default is reflecting CURRENT STATE, which is
# the legitimate use. Matched as substrings of the compared expression.
STATE_MARKERS = (
    "current", "selected", "self.page", "page", "target_index",
    "character_id", "battle.", "card.id", "pc.id", "s.value", "mode",
)


def _expression_text(node: ast.AST, source: str) -> str:
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:                                   # noqa: BLE001
        return ""


def main() -> int:
    failures: list[str] = []
    state_selects = 0
    checked = 0

    for path in sorted(pathlib.Path("bot").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "SelectOption" not in source:
            continue
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name != "SelectOption":
                continue

            default = next((kw for kw in node.keywords if kw.arg == "default"), None)
            if default is None:
                continue

            checked += 1
            text = _expression_text(default.value, source)
            lowered = text.lower()

            # Reflecting current state -- the correct use.
            if any(marker in lowered for marker in STATE_MARKERS):
                state_selects += 1
                continue

            failures.append(
                f"{path.as_posix()}:{default.value.lineno} marks a default from "
                f"{text!r}, which is a configured constant rather than the view's "
                f"current state. Discord treats a default option as already "
                f"selected, so picking it dispatches no interaction and the "
                f"option silently does nothing -- this is exactly how Standard "
                f"became unfightable on raids"
            )

    print(f"selects  : {checked} SelectOption(default=...) sites inspected")
    print(f"state    : {state_selects} legitimately reflect current state")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- no select pre-selects a value the player is meant to pick.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
