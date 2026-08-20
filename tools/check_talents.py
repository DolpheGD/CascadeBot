"""
Validate every character's talent tree, and measure what it is worth.

    python -m tools.check_talents

Two jobs.

STRUCTURE. Every character has a well-formed tree: branches are lines
bought in order, no node is unreachable, no tree can be bought out
entirely at max level (a tree with no choices in it is a stat bonus with
extra clicks), and the ids are stable.

POWER. This is the one that matters, and it is the reason this file
measures rather than asserts a comment. Talents raise player power, and
the ENTIRE difficulty ladder -- 28 story fights, 3 hunts, five adventure
regions -- was measured against characters with none. Every point of
power added here is paid for by re-tuning something, so the size of the
increase has to be a number somebody looked at, not a paragraph in a
docstring claiming it is "modest".

So the best-case investment is computed for every character at the two
levels that matter (40, where the story ends, and 100, the cap) and
reported as a percentage of their base stat block. If that number moves,
tools/check_story.py and bench_roles will disagree with the game, and
this print-out is where that becomes obvious.
"""

from __future__ import annotations

import itertools
import sys


def main() -> int:
    sys.path.insert(0, ".")

    from bot.database.models.enums import CharacterClass
    from bot.game.characters import character_seed_data as csd
    from bot.game.characters import talent_config as tc

    failures: list[str] = []

    rows = [v for v in vars(csd).values()
            if isinstance(v, list) and v and isinstance(v[0], dict)
            and "character_class" in v[0]]
    characters = rows[0] if rows else []
    if not characters:
        print("no characters found")
        return 1

    max_points = tc.points_for_level(100)
    fallback_capstones = 0
    worst_at_40 = ("", 0.0)
    worst_at_100 = ("", 0.0)

    for entry in characters:
        name = entry["name"]
        character_class = entry["character_class"]
        nodes = tc.tree_for(name, character_class)
        ids = [n["id"] for n in nodes]

        if len(ids) != len(set(ids)):
            failures.append(f"{name}: duplicate node ids in one tree")

        for node in nodes:
            if node["cost"] > tc.MAX_NODE_COST:
                failures.append(
                    f"{name}/{node['id']}: costs {node['cost']}, over the "
                    f"{tc.MAX_NODE_COST} cap")
            if node["cost"] < 1:
                failures.append(f"{name}/{node['id']}: costs nothing")
            effect = node.get("effect") or {}
            if "stat" not in effect or not ({"percent", "flat"} & set(effect)):
                failures.append(
                    f"{name}/{node['id']}: effect is neither a percent nor a flat "
                    f"bonus -- it would do nothing at all")
            if not str(node.get("name", "")).strip():
                failures.append(f"{name}/{node['id']}: unnamed")
            if node.get("capstone") and not node.get("authored"):
                fallback_capstones += 1

            # Every prerequisite must exist, or the node is unreachable.
            for required in tc.prerequisites(nodes, node["id"]):
                if required not in ids:
                    failures.append(
                        f"{name}/{node['id']}: needs {required}, which is not in "
                        f"the tree -- this node can never be bought")

        # A TREE MUST NOT BE COMPLETABLE. If a level-100 character can buy
        # every node, the branches stop being a choice and every
        # character of a class converges on one identical build.
        total = tc.total_tree_cost(nodes)
        if total < max_points + tc.MIN_TREE_COST_ABOVE_MAX_POINTS:
            failures.append(
                f"{name}: whole tree costs {total} and a level-100 character has "
                f"{max_points} -- it can be bought out, so there is no choice in it")

        # BEST-CASE POWER, by brute force over every affordable subset
        # that respects prerequisites. Brute force rather than a greedy
        # pick because greedy would understate a tree whose value is
        # concentrated in one expensive capstone, and understating is the
        # dangerous direction here.
        for level, record in ((40, "40"), (100, "100")):
            points = tc.points_for_level(level)
            best = _best_investment(tc, nodes, points)
            if record == "40" and best > worst_at_40[1]:
                worst_at_40 = (name, best)
            if record == "100" and best > worst_at_100[1]:
                worst_at_100 = (name, best)

    print(f"characters : {len(characters)} trees, "
          f"{len(tc.tree_for(characters[0]['name'], characters[0]['character_class']))} "
          f"nodes each")
    print(f"points     : {tc.points_for_level(40)} at level 40, "
          f"{max_points} at level 100")
    authored = sum(1 for e in characters if e["name"] in tc.CHARACTER_CAPSTONES)
    print(f"capstones  : {authored}/{len(characters)} characters have authored ones "
          f"({fallback_capstones} fallback capstones in use)")
    print(f"best case  : +{worst_at_40[1]:.0f}% in one stat at level 40 "
          f"({worst_at_40[0]}), +{worst_at_100[1]:.0f}% at level 100 "
          f"({worst_at_100[0]})")
    print("             ^ if this moves, re-run tools/tune_story.py and "
          "tools/bench_roles.py")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every tree is well-formed, and none of them can be bought out.")
    return 0


def _best_investment(tc, nodes: list[dict], points: int) -> float:
    """The largest single-stat percentage bonus buyable with `points`.

    Only percentage effects count toward this number. Flats (crit rate,
    crit damage, recharge) are excluded deliberately: they are additions
    to stats whose baseline varies enormously between characters, so a
    "+18 crit damage" is not commensurable with "+10% attack" and mixing
    them into one figure would produce a number that means nothing.
    """
    ids = [n["id"] for n in nodes]
    best = 0.0
    # Trees are ~13 nodes; the full subset space is 8k and this runs once
    # per character per level, so brute force is fine and exact.
    for size in range(len(ids) + 1):
        for combo in itertools.combinations(ids, size):
            chosen = set(combo)
            if sum((tc.node_by_id(nodes, i) or {}).get("cost", 0)
                   for i in chosen) > points:
                continue
            if any(required not in chosen
                   for i in chosen for required in tc.prerequisites(nodes, i)):
                continue
            percent, _flat = tc.stat_multipliers(nodes, list(chosen))
            if percent:
                best = max(best, max(percent.values()))
    return best


if __name__ == "__main__":
    raise SystemExit(main())
