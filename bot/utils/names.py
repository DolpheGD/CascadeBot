"""
Display names that fit without lying about what something is called.

THE PROBLEM. The battle screen is the most width-starved view in the game
and it renders names constantly -- party rows, enemy rows, turn order,
incoming-attack telegraphs. The declutter pass handled that by hard-
truncating to a character budget, which produced rows like
"Boss John's Drill…" and, in the 9-character turn order, "Wastelan…" --
two different Wasteland enemies rendering identically.

A truncated name is worse than a long one. The player can't tell which
enemy the telegraph means, and a name is the one piece of text in the UI
whose whole job is identification.

THE FIX, in order of preference:

  1. An AUTHORED short name (`short_name` on an enemy template). "Boss
     John's Driller Prototype" is "Driller Prototype" -- shorter, still
     unmistakably that enemy. This is the only mechanism that produces a
     good result, so it's the one the long names use.
  2. Automatic shortening that drops whole leading words rather than
     cutting mid-word, for anything that slipped through without an
     authored name.
  3. Ellipsis, as a last resort that should never actually fire. It
     exists so an arbitrarily long PLAYER-CHOSEN name (/rename allows 32
     characters) can't break the layout -- authored content should never
     reach it, and tools/check_ui_labels.py asserts that it doesn't.
"""

from __future__ import annotations

# Budgets, in visible characters.
#
# NAME_BUDGET is generous because a combatant's name sits on its OWN line
# in the battle rows (`**name** flags`, then HP on the next line), so it
# has nearly the full width to itself -- the old budget of 18 was
# inherited from the two-column layout that came before and was costing
# clarity for space that wasn't scarce any more.
#
# TURN_ORDER_BUDGET is genuinely tight: that line packs several names
# into one row, so it's the one place short names have to be short. It's
# set from the longest authored short name (see check_ui_labels), not
# guessed.
NAME_BUDGET = 28
TURN_ORDER_BUDGET = 16

# Words worth dropping first when shortening automatically: faction
# prefixes and generic qualifiers that several enemies share, so removing
# one loses the least information.
_DROPPABLE_PREFIXES = (
    "corrupted", "rogue", "the", "acatrya", "h-nation", "xender",
    "ocellios", "corporate", "wasteland", "propaganda", "tower",
)


def shorten(name: str, budget: int) -> str:
    """`name` reduced to at most `budget` visible characters.

    Drops whole leading words while any remain and the result is still
    more than one word -- "Acatrya Riot Trooper" becomes "Riot Trooper",
    never "Acatrya Riot Tro…". Only falls back to an ellipsis for a
    single word that is itself too long, which no authored name is."""
    if len(name) <= budget:
        return name

    words = name.split()
    while len(words) > 1 and len(" ".join(words)) > budget:
        if words[0].lower().rstrip("'s").rstrip("'") in _DROPPABLE_PREFIXES:
            words.pop(0)
        else:
            break

    candidate = " ".join(words)
    if len(candidate) <= budget:
        return candidate

    # Still too long: drop trailing words rather than cutting a word in
    # half, keeping at least the first.
    while len(words) > 1 and len(" ".join(words)) > budget:
        words.pop()
    candidate = " ".join(words)
    if len(candidate) <= budget:
        return candidate

    return candidate[: max(1, budget - 1)] + "…"


def display_name(combatant, budget: int = NAME_BUDGET) -> str:
    """What to call `combatant` in a width-limited view.

    Prefers the authored short name the template supplied, which is the
    whole point -- automatic shortening is a fallback for content that
    forgot to provide one, not the intended path."""
    name = getattr(combatant, "short_name", "") or combatant.name
    return shorten(name, budget)


def fit_suffix(name: str, suffix: str, limit: int) -> str:
    """`name` plus `suffix` inside `limit` characters, sacrificing the
    SUFFIX first.

    For select menus and buttons, where the label is a name plus metadata
    ("Lily Lovelace (Lv40, Sustain)"). Discord's limit applies to the
    whole label, so a naive `label[:100]` cuts whichever end happens to
    be last -- which, because the metadata is always appended, is exactly
    the thing that identifies the row when the name is long. Dropping the
    parenthetical instead keeps the label useful."""
    full = f"{name} {suffix}".strip()
    if len(full) <= limit:
        return full
    if len(name) <= limit:
        return name
    return shorten(name, limit)
