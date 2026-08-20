"""
Buying, refunding and applying talent nodes.

The rules are small and all of them are enforced HERE rather than in the
view, because the view is the one place that cannot be tested without a
Discord connection -- the same reason puzzles.solve lives outside the cog.

  * points available = level // POINTS_PER_LEVEL, minus what's spent
  * a node needs every earlier node in its branch already bought
  * respec is free and total; there is no partial refund, because a
    partial refund needs a rule for which nodes survive and every such
    rule strands somebody mid-branch
"""

from __future__ import annotations

from bot.game.characters import talent_config as tc


class TalentError(Exception):
    """Any reason a talent action can't proceed, phrased for the player."""


def tree(character) -> list[dict]:
    return tc.tree_for(character.template.name, character.template.character_class)


def bought(character) -> list[str]:
    return list(character.talents or [])


def spent_points(character) -> int:
    nodes = tree(character)
    return sum((tc.node_by_id(nodes, node_id) or {}).get("cost", 0)
               for node_id in bought(character))


def available_points(character) -> int:
    return tc.points_for_level(character.level) - spent_points(character)


def can_buy(character, node_id: str) -> tuple[bool, str]:
    nodes = tree(character)
    node = tc.node_by_id(nodes, node_id)
    if node is None:
        return False, "That talent doesn't exist."
    have = bought(character)
    if node_id in have:
        return False, f"**{node['name']}** is already learned."
    missing = [n for n in tc.prerequisites(nodes, node_id) if n not in have]
    if missing:
        earlier = tc.node_by_id(nodes, missing[0]) or {}
        return False, (f"**{node['name']}** needs **{earlier.get('name', missing[0])}** "
                       f"first — a branch is bought in order.")
    if node["cost"] > available_points(character):
        return False, (f"**{node['name']}** costs {node['cost']} point"
                       f"{'s' if node['cost'] != 1 else ''}; you have "
                       f"{available_points(character)}.")
    return True, ""


def buy(db, character, node_id: str) -> dict:
    ok, message = can_buy(character, node_id)
    if not ok:
        raise TalentError(message)
    # Reassigned wholesale, never appended in place: SQLAlchemy does not
    # detect a mutation inside a JSON value and the write is silently
    # lost on commit. Same rule as map_service's read_tiles.
    character.talents = bought(character) + [node_id]
    db.commit()
    return tc.node_by_id(tree(character), node_id)


def reset(db, character) -> int:
    """Unlearn everything. Returns the number of points handed back."""
    refunded = spent_points(character)
    character.talents = []
    db.commit()
    return refunded


def bonuses(character) -> tuple[dict, dict]:
    """(percent by stat, flat by stat) for what this character has
    bought. Used by combat.factory -- see base_character_stats."""
    return tc.stat_multipliers(tree(character), bought(character))


def summary(character) -> dict:
    """Everything the talent screen needs, in one read."""
    nodes = tree(character)
    have = bought(character)
    percent, flat = tc.stat_multipliers(nodes, have)
    branches: dict[str, list[dict]] = {}
    for node in sorted(nodes, key=lambda n: (n["branch"], n["tier"])):
        branches.setdefault(node["branch_name"], []).append({
            **node,
            "bought": node["id"] in have,
            "buyable": can_buy(character, node["id"])[0],
        })
    return {
        "branches": branches,
        "spent": spent_points(character),
        "available": available_points(character),
        "total": tc.points_for_level(character.level),
        "percent": percent,
        "flat": flat,
    }
