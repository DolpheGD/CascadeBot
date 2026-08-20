"""
Assert that every key an ability declares is a key the engine reads.

    python -m tools.check_effect_keys

----------------------------------------------------------------------
THE BUG THIS EXISTS FOR
----------------------------------------------------------------------
Slikrz's ultimate said "all damage-over-time on them hits 70% harder".
Its effect said:

    {"kind": "team_dot_amplify", "percent": 70, "max_stacks": 3, ...}

and the engine reads `percent_per_stack`, not `percent`. So the 70 was
never used, the mark ran at the 15% default, and the ability had been
doing 45% at full stacks against an advertised 70% since the day it was
written.

Nothing caught it, and it's worth being precise about why:

  * check_descriptions asserts every % in the text appears SOMEWHERE in
    the effect. 70 did appear -- under a key nothing reads. Its rule is
    about presence, not use.
  * check_runtime executes encounters, not character kits.
  * check_resonance only asks whether SOME number changes at R4.
  * The ability worked. It logged, it dealt damage, it applied a mark.
    It was just quietly the wrong size, which is the one failure mode a
    smoke test cannot see.

A dead key is uniquely nasty because it is invisible from both ends: the
config looks deliberate, and the engine looks correct. Only the pairing
is wrong, and nothing in the codebase previously looked at the pairing.

----------------------------------------------------------------------
HOW IT WORKS
----------------------------------------------------------------------
Static, and deliberately so -- a runtime check would have to actually
cast every ability under every condition to prove a key is never read.

  1. Parse bot/game/combat/effects.py.
  2. For each function, record which `effect[...]` / `effect.get(...)`
     string keys it reads, and which other functions it calls.
  3. Split resolve_active_ability's body into its `kind == "..."`
     branches, and resolve each branch's key set transitively through
     the helpers it calls (so keys read inside _apply_dot_vulnerability
     count for the three kinds that call it).
  4. Keys read OUTSIDE the branch dispatch apply to every kind -- e.g.
     poise_damage_for(ability) runs once for all abilities.
  5. Every ability in every kit and gear pool is then checked against
     the key set for its own kind.

Where the analysis genuinely cannot see through (a key consumed by a
sibling system rather than by effects.py), the key is listed in
KEYS_READ_ELSEWHERE with the reason. That list is the honest part: it
should stay short, and every entry should name who does the reading.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# TRIGGER STRINGS THE ENGINE ACTUALLY DISPATCHES ON.
#
# A passive's `trigger` is compared as a literal in effects.py. Three of
# those comparisons GATE the passive entirely -- get the string wrong and
# the ability loads, validates, prints its description on the info page
# and never fires. Everything else is documentation: the retaliation and
# damage-reduction kinds are found by find_passive(kind) inside the hit
# resolver and never look at `trigger` at all.
#
# Two abilities shipped in one sitting with near-miss triggers:
# "turn_start" for "on_turn_start", and "on_hit_taken" for a kind that
# is not trigger-dispatched at all. Both were single occurrences of a
# string used nowhere else in the file, which is exactly the shape this
# checks for -- a typo is, almost by definition, a value with a
# population of one.
DISPATCHED_TRIGGERS = {"on_kill", "on_low_hp", "on_turn_start"}

# Values that are legal but purely descriptive. Anything outside both
# sets is either a typo or a trigger someone expected the engine to
# honour and it does not.
DOCUMENTARY_TRIGGERS = {
    "always", "on_crit", "on_heal", "on_shield", "on_buff", "on_break",
    "on_dot", "on_hit_debuffed", "on_sacrifice", "on_cleanse", "on_ultimate",
}

import ast
import pathlib
import sys

EFFECTS = pathlib.Path("bot/game/combat/effects.py")

# Keys that are structural rather than parameters.
STRUCTURAL = {"kind"}

# Keys read by something OTHER than effects.py's branch for that kind.
# Each entry must name the reader, so this can't quietly become a
# suppression list for real bugs.
KEYS_READ_ELSEWHERE = {
    # factory.py scales these at Resonance 4 (see _KIT_MAGNITUDE_KEYS,
    # _KIT_POISE_KEYS, _KIT_INVERSE_KEYS). They're read there, not here.
    "hp_per_point",
    # combat_ui / embedder read these for display and targeting.
    "damage_stat",
    # poise_damage_for(ability) reads this off the ability for EVERY
    # attack, before the dispatch -- see the _ability_poise binding at
    # the top of resolve_active_ability.
    "poise_damage",
}


def _key_of(node: ast.AST) -> str | None:
    """The literal string key in `effect["x"]` or `effect.get("x", ...)`."""
    if isinstance(node, ast.Subscript):
        target, index = node.value, node.slice
        if isinstance(target, ast.Name) and target.id == "effect" \
                and isinstance(index, ast.Constant) and isinstance(index.value, str):
            return index.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "get" \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "effect" \
            and node.args and isinstance(node.args[0], ast.Constant) \
            and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


def _scan(nodes) -> tuple[set[str], set[str]]:
    """(effect keys read, function names called) anywhere under `nodes`."""
    keys: set[str] = set()
    calls: set[str] = set()
    for root in nodes:
        for node in ast.walk(root):
            key = _key_of(node)
            if key:
                keys.add(key)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)
    return keys, calls


def _branch_kinds(test: ast.AST) -> set[str]:
    """The kind literals a branch test matches: kind == "x", or
    kind in ("x", "y")."""
    kinds: set[str] = set()
    for node in ast.walk(test):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) \
                and node.left.id == "kind":
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    kinds.add(comparator.value)
                elif isinstance(comparator, (ast.Tuple, ast.List, ast.Set)):
                    kinds.update(e.value for e in comparator.elts
                                 if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return kinds


def build_key_map() -> tuple[dict[str, set[str]], set[str]]:
    """(kind -> keys the engine reads for it, keys read for every kind)."""
    tree = ast.parse(EFFECTS.read_text(encoding="utf-8"))

    # Per-function keys and calls, for transitive resolution.
    per_function: dict[str, tuple[set[str], set[str]]] = {}
    resolver = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            per_function[node.name] = _scan(node.body)
            if node.name == "resolve_active_ability":
                resolver = node
    if resolver is None:
        raise SystemExit("resolve_active_ability not found -- has effects.py moved?")

    def transitive(name: str, seen: set[str] | None = None) -> set[str]:
        seen = seen or set()
        if name in seen or name not in per_function:
            return set()
        seen.add(name)
        keys, calls = per_function[name]
        for callee in calls:
            keys |= transitive(callee, seen)
        return keys

    # Walk the resolver's top-level if/elif chain.
    by_kind: dict[str, set[str]] = {}
    universal: set[str] = set()

    def visit(statements) -> None:
        nonlocal universal
        for stmt in statements:
            if isinstance(stmt, ast.If) and _branch_kinds(stmt.test):
                kinds = _branch_kinds(stmt.test)
                keys, calls = _scan(stmt.body)
                for callee in calls:
                    keys |= transitive(callee)
                for kind in kinds:
                    by_kind.setdefault(kind, set()).update(keys)
                visit(stmt.orelse)      # the elif chain continues here
            elif isinstance(stmt, ast.If):
                visit(stmt.body)
                visit(stmt.orelse)
            else:
                # Outside the dispatch: applies to every kind.
                #
                # DIRECT READS ONLY -- deliberately not resolved through
                # called helpers, unlike the branches above. The
                # resolver defines a nested `_hit` wrapper before the
                # dispatch, and resolving that transitively drags in
                # every key the generic hit path can read anywhere,
                # which lands `percent` and `percent_per_stack` in the
                # universal set. That made the check pass Slikrz's bug,
                # i.e. made it useless for the one thing it was written
                # to catch: with those keys universal, no ability could
                # ever declare a dead one.
                #
                # Anything genuinely read for every kind by a helper
                # goes in KEYS_READ_ELSEWHERE, named, instead of being
                # inferred.
                keys, _calls = _scan([stmt])
                universal |= keys

    visit(resolver.body)
    return by_kind, universal


def abilities_to_check() -> list[tuple[str, str, dict]]:
    """(where, name, effect) for every authored ability in the game."""
    from bot.game.combat import skills

    found: list[tuple[str, str, dict]] = []
    for label, source in (
        ("kit", skills.CHARACTER_KIT_MAP),
        ("passive", skills.CHARACTER_PASSIVE_MAP),
    ):
        for key, ability in source.items():
            if isinstance(ability, dict) and isinstance(ability.get("effect"), dict):
                found.append((label, key, ability["effect"]))

    for name in dir(skills):
        value = getattr(skills, name)
        if not isinstance(value, dict) or name.endswith("_MAP"):
            continue
        for key, ability in value.items():
            if isinstance(ability, dict) and isinstance(ability.get("effect"), dict):
                found.append((f"{name}", str(key), ability["effect"]))
    return found


def main() -> int:
    by_kind, universal = build_key_map()
    failures: list[str] = []
    checked = 0

    for where, name, effect in abilities_to_check():
        kind = effect.get("kind")
        if kind is None or kind not in by_kind:
            # A kind with no branch is a separate problem, and one
            # check_runtime already surfaces by executing it.
            continue
        readable = by_kind[kind] | universal | STRUCTURAL | KEYS_READ_ELSEWHERE
        for key in effect:
            checked += 1
            if key not in readable:
                failures.append(
                    f"{where} '{name}' ({kind}) declares '{key}', which the engine "
                    f"never reads for that kind -- the value is silently ignored. "
                    f"Keys it does read: {', '.join(sorted(by_kind[kind])) or '(none)'}"
                )

    # ---- trigger strings ---------------------------------------------
    #
    # Same failure as an unread key, one field over: a passive whose
    # trigger the dispatcher never matches is silently inert.
    from bot.game.loot.abilities import ARMOR_PASSIVES

    known = DISPATCHED_TRIGGERS | DOCUMENTARY_TRIGGERS
    triggers_checked = 0
    for passive in ARMOR_PASSIVES:
        trigger = passive.get("trigger")
        if trigger is None:
            continue
        triggers_checked += 1
        if trigger not in known:
            close = [k for k in sorted(known)
                     if k.endswith(trigger) or trigger.endswith(k) or k in trigger]
            hint = f" Did you mean {close[0]!r}?" if close else ""
            failures.append(
                f"armor passive '{passive['id']}' has trigger {trigger!r}, which "
                f"appears nowhere in the engine.{hint} A trigger the dispatcher "
                f"never matches means the passive loads, validates, prints its "
                f"description and never once fires"
            )

    print(f"kinds    : {len(by_kind)} effect kinds resolved from effects.py")
    print(f"universal: {len(universal)} keys read for every kind")
    print(f"keys     : {checked} declared across every kit, passive and gear pool")
    print(f"triggers : {triggers_checked} passive triggers, "
          f"{len(DISPATCHED_TRIGGERS)} of which the engine dispatches on")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every key an ability declares is a key the engine actually reads.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
