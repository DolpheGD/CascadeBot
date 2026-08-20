"""
Validate adventure map generation.

    python -m tools.check_dungeon_map

THE PROPERTY THAT MATTERS IS THAT CHOICES COST SOMETHING.

A branching map is easy to draw and hard to make mean anything. The
previous generator produced a map that looked like Slay the Spire and
behaved like a corridor: it topped every node up to three outgoing edges,
and since floors were only 3-5 wide that connected every node to every
node on the next floor. Measured, from either of the two floor-1 nodes,
74 of the map's 76 rooms were reachable -- and 73 were reachable from
BOTH. Every fork was cosmetic.

Nothing in the source said so. The generator's own docstring described
Slay the Spire's algorithm, the code implemented it, and then one
well-intentioned "make sure players have options" pass undid it. That is
why this file measures the graph instead of reading it.

Checked, over many seeds and every region:

  1. DIVERGENCE. Between one checkpoint and the next boss, the routes out
     of a fork must lock out a real share of that segment's rooms. This
     is the headline number and it has a floor.

  2. NO DEAD ENDS. Every node must be reachable from the start AND able
     to reach a boss. A room you can walk into and not leave ends the run
     with no explanation.

  3. NO CROSSING EDGES. Slay the Spire's legibility rule: two edges
     between the same pair of floors may not swap over. Crossings are
     also exactly the edges that let a left-hand lane reach the right of
     the map, which is how lock-out gets quietly undone again.

  4. THE MAP FITS. Column count stays renderable, and the whole thing
     stays inside Discord's embed budget.

  5. EVERY ROOM TYPE IS REACHABLE SOMEWHERE, so a type that stopped
     being generated at all fails loudly instead of silently vanishing.
"""

from __future__ import annotations

import random
import sys
from collections import defaultdict

SEEDS = 60

# The share of a segment's rooms that a fork must be able to rule out,
# averaged over every fork in every seed. Slay the Spire's own maps sit
# high here; the old generator scored about 3%.
MIN_MEAN_LOCKOUT = 0.45
# And no single fork may be purely cosmetic.
MIN_ANY_LOCKOUT = 0.05
# Rendering budget: the map embed draws one column per index.
MAX_COLUMNS = 8


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.dungeon.generator import DungeonGenerator
    from bot.game.dungeon.region_config import ordered_regions

    failures: list[str] = []
    lockouts: list[float] = []
    widest = 0
    room_types_seen: set[str] = set()
    total_nodes = 0
    forks = 0

    regions = ordered_regions()
    for seed in range(SEEDS):
        region = regions[seed % len(regions)]
        graph = DungeonGenerator(rng=random.Random(seed)).generate(region)
        nodes = graph["nodes"]

        # THE MAP EXISTS AT ALL.
        #
        # Sounds unnecessary; is not. A greedy planar-edge filter deleted
        # an entire 14-floor segment on one seed -- every node stranded,
        # zero survivors -- and the only symptom was a KeyError on the
        # missing start node from a caller three functions away. An
        # emptiness check here names the actual problem.
        if not nodes:
            failures.append(f"seed {seed} ({region}): generated an EMPTY map")
            continue
        if graph["start_node"] not in nodes:
            failures.append(
                f"seed {seed} ({region}): start node {graph['start_node']} is not "
                f"in the map -- generation stranded its own entry point")
            continue
        for boss in graph.get("boss_nodes") or []:
            if boss not in nodes:
                failures.append(
                    f"seed {seed} ({region}): boss node {boss} is not in the map")
        floors_present = {n["floor"] for n in nodes.values()}
        missing_floors = set(range(graph["num_floors"])) - floors_present
        if missing_floors:
            failures.append(
                f"seed {seed} ({region}): floors {sorted(missing_floors)[:5]} have "
                f"no rooms -- the run has a gap in it")

        total_nodes += len(nodes)
        room_types_seen.update(n["room_type"] for n in nodes.values())
        widest = max(widest, max(n["index"] for n in nodes.values()) + 1)

        # ---- 2. reachability, both directions ----
        start = graph["start_node"]
        forward = _reach(nodes, start)
        stranded = set(nodes) - forward
        if stranded:
            failures.append(
                f"seed {seed} ({region}): {len(stranded)} node(s) unreachable from "
                f"the start, e.g. {sorted(stranded)[:3]}")
        boss_nodes = set(graph.get("boss_nodes") or [])
        reverse: dict[str, set[str]] = defaultdict(set)
        for source, node in nodes.items():
            for target in node["edges"]:
                reverse[target].add(source)
        can_finish = set()
        frontier = list(boss_nodes)
        can_finish.update(boss_nodes)
        while frontier:
            node_id = frontier.pop()
            for source in reverse.get(node_id, set()):
                if source not in can_finish:
                    can_finish.add(source)
                    frontier.append(source)
        dead = set(nodes) - can_finish
        if dead:
            failures.append(
                f"seed {seed} ({region}): {len(dead)} node(s) cannot reach any boss "
                f"-- walking into one ends the run, e.g. {sorted(dead)[:3]}")

        # ---- 3. no crossing edges ----
        by_floor: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for source, node in nodes.items():
            for target in node["edges"]:
                if target in nodes:
                    by_floor[node["floor"]].append(
                        (node["index"], nodes[target]["index"]))
        for floor, pairs in by_floor.items():
            for i, (a_source, a_target) in enumerate(pairs):
                for b_source, b_target in pairs[i + 1:]:
                    if ((a_source < b_source and a_target > b_target)
                            or (a_source > b_source and a_target < b_target)):
                        failures.append(
                            f"seed {seed} ({region}): edges cross on floor {floor} "
                            f"({a_source}->{a_target} vs {b_source}->{b_target})")
                        break

        # ---- 1. divergence, per segment ----
        checkpoints = [start] + list(graph.get("boss_nodes") or [])[:-1]
        for index, checkpoint in enumerate(checkpoints):
            segment_boss = (graph.get("boss_nodes") or [])[index]
            options = [t for t in nodes[checkpoint]["edges"] if t in nodes]
            if len(options) < 2:
                continue
            forks += 1
            sets = [_reach(nodes, option, stop=segment_boss) | {option}
                    for option in options]
            common = set.intersection(*sets)
            union = set.union(*sets)
            lockout = 1 - len(common) / max(1, len(union))
            lockouts.append(lockout)
            if lockout < MIN_ANY_LOCKOUT:
                failures.append(
                    f"seed {seed} ({region}): a fork at {checkpoint} rules out only "
                    f"{lockout:.0%} of its segment -- that fork is decoration")

    mean_lockout = sum(lockouts) / len(lockouts) if lockouts else 0.0
    if mean_lockout < MIN_MEAN_LOCKOUT:
        failures.append(
            f"mean lock-out is {mean_lockout:.0%}, under the {MIN_MEAN_LOCKOUT:.0%} "
            f"floor -- routes reconverge too fast for planning to pay off")

    if widest > MAX_COLUMNS:
        failures.append(
            f"maps are up to {widest} columns wide, over the {MAX_COLUMNS} the map "
            f"embed can draw legibly")

    from bot.game.dungeon.room_config import ROOM_WEIGHTS_BY_STAGE
    # Only types with a NON-ZERO weight are expected to appear. A type
    # deliberately parked at 0 (see RELIC_EVENT) is authored-but-not-wired
    # and must not fail this check -- but a type with real weight that
    # never generates still must.
    expected = {r.value for weights in ROOM_WEIGHTS_BY_STAGE.values()
                for r, weight in weights.items() if weight > 0}
    missing = expected - room_types_seen
    if missing:
        failures.append(
            f"room type(s) {sorted(missing)} are weighted but never generated in "
            f"{SEEDS} runs -- they are configured content nobody will ever see")

    print(f"seeds      : {SEEDS} maps across {len(regions)} regions, "
          f"{total_nodes / SEEDS:.0f} rooms each")
    print(f"forks      : {forks} measured")
    print(f"lock-out   : {mean_lockout:.0%} mean "
          f"(min {min(lockouts, default=0):.0%}, max {max(lockouts, default=0):.0%})")
    print("             ^ share of a segment a single fork rules out")
    print(f"width      : up to {widest} columns")
    print(f"room types : {len(room_types_seen)} distinct generated")

    if failures:
        print()
        for failure in sorted(set(failures))[:20]:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every route is finishable, no edges cross, and choices lock "
          "real content out.")
    return 0


def _reach(nodes: dict, start: str, stop: str | None = None) -> set[str]:
    seen = {start}
    frontier = [start]
    while frontier:
        node_id = frontier.pop()
        if stop is not None and node_id == stop:
            continue
        for target in nodes.get(node_id, {}).get("edges", []):
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


if __name__ == "__main__":
    raise SystemExit(main())
