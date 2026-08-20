"""
Generates the per-expedition dungeon graph stored in Expedition.graph.

Approach (same family as Slay the Spire's map generation): walk several
random paths from the start floor to the boss floor, letting each path drift
left/right by at most one node per floor. The union of every path's nodes
and edges becomes the graph -- this guarantees every node is reachable from
start and the boss is reachable from every node, without needing a separate
connectivity-repair pass.

Room types are assigned afterward: START/BOSS are fixed, the floor
immediately before each boss is forced to be all CAMPFIRE (so the player can
always heal up before the fight), and everything else is weighted-random per
room_config.py, subject to per-run caps and the "no elite too early" rule.

Adventure Overhaul: a single expedition now contains 2-4 REGULAR boss fights
plus one guaranteed, tougher FINAL boss at the very end -- see
room_config.NUM_REGULAR_BOSSES_WEIGHTS. Internally this is built as several
independently-generated "segments" (each its own mini dungeon ending in a
boss floor) stitched together: segment N+1's own START node is discarded
and its edges are reattached directly to segment N's boss node, so the
boss node itself becomes the next segment's entry point. Only the FINAL
segment's boss ends the expedition (see resolve_battle_end in
bot/services/dungeon_service.py) -- earlier bosses are big, rewarding
checkpoints along a longer run. Which enemy template a BOSS floor actually
gets (a regular boss vs a final-boss-caliber one) is decided at combat-
start time by enemy_catalog.get_boss_encounter, based on whether that
node is the last entry in graph["boss_nodes"] -- the generator itself
doesn't need to know or care which segment is "the final one".

Output shape (JSON-serializable, matches Expedition.graph):

    {
        "region": "Whispering Forest",
        "num_floors": 9,
        "start_node": "0_0",
        "boss_node": "8_0",        # final boss (back-compat single value)
        "boss_nodes": ["8_0"],     # every boss in the run, in order
        "nodes": {
            "0_0": {"floor": 0, "index": 0, "room_type": "start",
                     "edges": ["1_0", "1_1"], "completed": false},
            ...
        }
    }
"""

from __future__ import annotations

import random

from bot.database.models.enums import RoomType
from bot.game.dungeon.room_config import (
    ELITE_MIN_FLOOR_INDEX,
    MID_REST_MIN_SEGMENT_FLOORS,
    MAX_PER_RUN,
    REST_FLOOR_WIDTH,
    ROOM_WEIGHTS_BY_STAGE,
    SEGMENT_FLOOR_RANGE,
    roll_num_regular_bosses,
)


def mid_rest_floor_for(num_floors: int) -> int | None:
    """Which floor of a segment gets the extra campfire, or None.

    Defined ONCE and imported by both the floor-width builder and the
    room-type assigner. The first version computed `rest_floor // 2`
    independently in each, which is two code paths deriving one value --
    they agreed on the index and disagreed on the WIDTH, so the mid rest
    came out as a full 4-7 wide floor of campfires and the run averaged
    18 rest rooms instead of 7.
    """
    if num_floors < MID_REST_MIN_SEGMENT_FLOORS:
        return None
    return max(2, (num_floors - 2) // 2)


class DungeonGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    def generate(
        self,
        region: str,
        num_floors: int | None = None,
        num_bosses: int | None = None,
        # FEWER PATHS, WIDER FLOORS.
        #
        # Divergence is a ratio: paths drawn versus columns available. Ten
        # paths across a 3-5 wide floor visits essentially every node
        # every time, so the map has the same shape on every run and every
        # lane touches every other. Six paths across 4-7 columns leaves
        # real gaps -- some columns are empty on some floors, and a lane
        # that goes left genuinely cannot come back.
        num_paths: int = 6,
        min_width: int = 4,
        max_width: int = 7,
    ) -> dict:
        """If `num_bosses` isn't given, it's rolled as 2-4 REGULAR bosses
        (room_config.NUM_REGULAR_BOSSES_WEIGHTS) plus one guaranteed extra
        FINAL boss segment on top -- so the total segment count produced
        here is 3-5. If `num_floors` isn't given, each boss segment
        independently rolls a length from room_config.SEGMENT_FLOOR_RANGE
        (so total length scales with num_bosses). Passing `num_floors`
        explicitly forces a single segment of exactly that length (used
        by tests/tools that want the old fixed-length behavior)."""
        num_bosses = num_bosses or (roll_num_regular_bosses(self.rng) + 1)

        if num_floors is not None:
            segment_lengths = [num_floors]
        else:
            segment_lengths = [
                self.rng.randint(*SEGMENT_FLOOR_RANGE) for _ in range(num_bosses)
            ]

        combined_nodes: dict[str, dict] = {}
        boss_nodes: list[str] = []
        floor_offset = 0
        # Shared across every segment so MAX_PER_RUN is a run-wide cap.
        run_counts: dict = {}

        for seg_index, seg_floors in enumerate(segment_lengths):
            if seg_floors < 4:
                raise ValueError("each boss segment needs at least 4 floors")

            segment = self._generate_segment(seg_floors, num_paths, min_width,
                                             max_width, run_counts)

            if seg_index == 0:
                for local_id, node in segment.items():
                    combined_nodes[local_id] = self._offset_node(node, floor_offset)
            else:
                # Segment N+1's own "0_0" start node is discarded -- the
                # previous segment's boss node (already in combined_nodes,
                # sitting at exactly floor_offset) becomes its entry point
                # instead. Every other node/edge just shifts by floor_offset.
                local_start = segment["0_0"]
                prev_boss_id = self._make_id(floor_offset, 0)

                redirected_edges = {
                    self._make_id(floor_offset + self._parse_id(e)[0], self._parse_id(e)[1])
                    for e in local_start["edges"]
                }
                combined_nodes[prev_boss_id]["edges"] = sorted(
                    set(combined_nodes[prev_boss_id]["edges"]) | redirected_edges
                )

                for local_id, node in segment.items():
                    if local_id == "0_0":
                        continue
                    new_id = self._make_id(floor_offset + node["floor"], node["index"])
                    combined_nodes[new_id] = self._offset_node(node, floor_offset)

            boss_floor = floor_offset + seg_floors - 1
            boss_id = self._make_id(boss_floor, 0)
            boss_nodes.append(boss_id)
            floor_offset = boss_floor

        total_floors = floor_offset + 1

        return {
            "region": region,
            "num_floors": total_floors,
            "num_bosses": len(boss_nodes),
            "start_node": self._make_id(0, 0),
            "boss_node": boss_nodes[-1],
            "boss_nodes": boss_nodes,
            "nodes": combined_nodes,
        }

    @staticmethod
    def _offset_node(node: dict, floor_offset: int) -> dict:
        new_floor = node["floor"] + floor_offset
        return {
            "floor": new_floor,
            "index": node["index"],
            "room_type": node["room_type"],
            "edges": sorted(
                DungeonGenerator._make_id(
                    DungeonGenerator._parse_id(e)[0] + floor_offset, DungeonGenerator._parse_id(e)[1]
                )
                for e in node["edges"]
            ),
            "completed": False,
        }

    # ------------------------------------------------------------------
    # One self-contained segment: floors 0..num_floors-1, local numbering,
    # start node at "0_0", boss node at "{num_floors-1}_0". Exactly the old
    # single-boss generate() logic, factored out so generate() can call it
    # once per boss.
    # ------------------------------------------------------------------
    def _generate_segment(
        self, num_floors: int, num_paths: int, min_width: int, max_width: int,
        run_counts: dict | None = None,
    ) -> dict[str, dict]:
        floor_widths = self._build_floor_widths(num_floors, min_width, max_width)
        nodes, edges = self._walk_paths(floor_widths, num_paths)

        # NO DENSIFICATION. This used to top every node up to 3 outgoing
        # edges, which on a 3-wide floor means "connect to all of them" --
        # a complete bipartite graph between consecutive floors. Measured
        # on the old generator: from either floor-1 node, 74 of the map's
        # 76 nodes were reachable, and 73 were reachable from BOTH. The
        # map branched visually and locked out nothing at all, which is
        # exactly the "your choices don't really matter" this replaces.
        #
        # Instead the raw walk is left sparse and then made LEGIBLE:
        edges = self._remove_crossings(edges)
        nodes, edges = self._prune_unreachable(floor_widths, nodes, edges)
        room_types = self._assign_room_types(floor_widths, nodes, run_counts)

        node_data = {}
        for node_id in nodes:
            floor, index = self._parse_id(node_id)
            node_data[node_id] = {
                "floor": floor,
                "index": index,
                "room_type": room_types[node_id].value,
                "edges": sorted(edges.get(node_id, [])),
                "completed": False,
            }
        return node_data

    # ------------------------------------------------------------------
    # Floor layout
    # ------------------------------------------------------------------
    def _build_floor_widths(self, num_floors: int, min_width: int, max_width: int) -> list[int]:
        widths = [1]  # floor 0: start (or, for segments 2+, the previous boss)
        for _ in range(num_floors - 3):  # middle floors
            widths.append(self.rng.randint(min_width, max_width))
        widths.append(REST_FLOOR_WIDTH)  # forced rest floor before boss
        widths.append(1)  # boss floor

        # The mid-segment rest is narrowed to the same width as the
        # pre-boss one. Left at full width it was a 4-7 wide bank of
        # campfires and the run averaged 18 rest rooms; a rest is meant
        # to be a decision about routing, not a floor you cannot miss.
        mid_rest = mid_rest_floor_for(num_floors)
        if mid_rest is not None and 0 < mid_rest < len(widths) - 2:
            widths[mid_rest] = REST_FLOOR_WIDTH
        return widths

    # ------------------------------------------------------------------
    # Path walking -> nodes & edges
    # ------------------------------------------------------------------
    def _walk_paths(
        self, floor_widths: list[int], num_paths: int
    ) -> tuple[set[str], dict[str, set[str]]]:
        nodes: set[str] = {self._make_id(0, 0)}
        edges: dict[str, set[str]] = {}

        for path in range(num_paths):
            # THE FIRST STEP FANS OUT ACROSS THE WHOLE FLOOR.
            #
            # Every path used to start at column 0 and drift by at most
            # one, so floor 1 only ever held columns 0-1 no matter how
            # wide the floor was, and every route was squeezed through the
            # same two nodes before it could spread. Divergence measured
            # 0-18% of the map locked out, and on some seeds the run
            # opened with a single option -- a fork that is not a fork.
            #
            # Seeding each path at its own column across the full width
            # is what makes the opening choice a real one: the left lane
            # and the right lane start far enough apart that ±1 steps
            # cannot reconcile them before the boss.
            first_width = floor_widths[1] if len(floor_widths) > 1 else 1
            if num_paths >= first_width:
                # Spread deterministically first so every column is used
                # at least once, then let the extras land randomly.
                idx = (path % first_width if path < first_width
                       else self.rng.randrange(first_width))
            else:
                idx = self.rng.randrange(first_width)

            start_id = self._make_id(0, 0)
            first_id = self._make_id(1, idx)
            nodes.add(start_id)
            nodes.add(first_id)
            edges.setdefault(start_id, set()).add(first_id)

            for floor in range(1, len(floor_widths) - 1):
                next_width = floor_widths[floor + 1]
                step = self.rng.choice([-1, 0, 1])
                next_idx = max(0, min(next_width - 1, idx + step))

                current_id = self._make_id(floor, idx)
                next_id = self._make_id(floor + 1, next_idx)

                nodes.add(current_id)
                nodes.add(next_id)
                edges.setdefault(current_id, set()).add(next_id)

                idx = next_idx

        return nodes, edges

    # ------------------------------------------------------------------
    # NON-CROSSING EDGES
    #
    # Slay the Spire's load-bearing map rule, and the reason its maps read
    # as separate routes rather than as a mesh: two edges between the same
    # pair of floors may not cross. If (a -> j) and (b -> i) both exist
    # with a < b and i < j, the lines visually swap over and the two
    # "lanes" merge into one blob.
    #
    # It matters mechanically as well as visually. Crossing edges are
    # precisely the ones that let a player on the left of the map reach
    # the right of it, which is how a map stops locking anything out.
    # Removing them is what makes a lane a commitment.
    # ------------------------------------------------------------------
    def _remove_crossings(self, edges: dict[str, set[str]]) -> dict[str, set[str]]:
        """Keep a planar (non-crossing) edge set, and never strand a node.

        MONOTONE, NOT GREEDY-REJECT. The first version of this walked the
        edges in sorted order and dropped any that crossed something
        already kept. That is a correct description of "non-crossing" and
        a terrible algorithm: an early wide edge like (0 -> 3) rejects
        every later edge that passes under it, the rejections cascade
        floor by floor, and on seed 35 it deleted an ENTIRE 14-floor
        segment -- every node stranded, zero survivors, and the run
        crashed on the missing start node.

        A layered edge set is planar exactly when, reading sources left to
        right, the targets never go backwards. So that is the rule: sort
        by (source, target) and keep an edge only if its target is at
        least the highest target kept so far. This is O(n), always
        planar, and cannot cascade.

        The monotone pass can still leave a node with nothing attached, so
        two repairs follow. Both attach to the CURRENT highest target,
        which is always safe: two edges sharing a target never cross, and
        neither does an edge to a target at or above the running maximum.
        """
        by_floor: dict[int, list[tuple[int, int]]] = {}
        for source, targets in edges.items():
            floor, index = self._parse_id(source)
            for target in targets:
                _, target_index = self._parse_id(target)
                by_floor.setdefault(floor, []).append((index, target_index))

        kept: dict[str, set[str]] = {}
        for floor, pairs in by_floor.items():
            ordered = sorted(set(pairs))
            sources = sorted({s for s, _t in ordered})
            targets = sorted({t for _s, t in ordered})

            survivors: list[tuple[int, int]] = []
            highest = -1
            for source_index, target_index in ordered:
                if target_index >= highest:
                    survivors.append((source_index, target_index))
                    highest = target_index

            # Repair 1: every source keeps a way forward.
            attached_sources = {s for s, _t in survivors}
            for source_index in sources:
                if source_index in attached_sources:
                    continue
                # The highest target at-or-below what this source could
                # legally reach, clamped into the planar order.
                reachable = [t for _s, t in survivors if _s <= source_index]
                target_index = max(reachable) if reachable else targets[0]
                survivors.append((source_index, target_index))

            # Repair 2: every target keeps a way in, so no room is drawn
            # on the map with nothing pointing at it.
            attached_targets = {t for _s, t in survivors}
            for target_index in targets:
                if target_index in attached_targets:
                    continue
                candidates = [s for s, t in survivors if t <= target_index]
                source_index = max(candidates) if candidates else sources[0]
                survivors.append((source_index, target_index))

            for source_index, target_index in survivors:
                kept.setdefault(self._make_id(floor, source_index), set()).add(
                    self._make_id(floor + 1, target_index))
        return kept

    # ------------------------------------------------------------------
    # PRUNE ANYTHING NOT ON A START-TO-BOSS ROUTE
    #
    # Removing crossings can strand a node -- reachable from the start but
    # with nowhere to go, or reachable from nothing. A node you can walk
    # into and not leave is a dead end that ends the run, and a node
    # nothing points at is drawn on the map and unreachable. Both are
    # worse than not existing, so both are deleted.
    # ------------------------------------------------------------------
    def _prune_unreachable(
        self, floor_widths: list[int], nodes: set[str], edges: dict[str, set[str]]
    ) -> tuple[set[str], dict[str, set[str]]]:
        last_floor = len(floor_widths) - 1
        start = self._make_id(0, 0)

        forward = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for target in edges.get(current, set()):
                if target not in forward:
                    forward.add(target)
                    frontier.append(target)

        # Backward from the boss floor, over reversed edges.
        reverse: dict[str, set[str]] = {}
        for source, targets in edges.items():
            for target in targets:
                reverse.setdefault(target, set()).add(source)
        boss_nodes = {n for n in nodes if self._parse_id(n)[0] == last_floor}
        backward = set(boss_nodes)
        frontier = list(boss_nodes)
        while frontier:
            current = frontier.pop()
            for source in reverse.get(current, set()):
                if source not in backward:
                    backward.add(source)
                    frontier.append(source)

        alive = forward & backward
        trimmed = {
            source: {t for t in targets if t in alive}
            for source, targets in edges.items() if source in alive
        }
        return alive, trimmed

    # ------------------------------------------------------------------
    # Room type assignment
    # ------------------------------------------------------------------
    def _assign_room_types(
        self, floor_widths: list[int], nodes: set[str],
        run_counts: dict | None = None,
    ) -> dict[str, RoomType]:
        last_floor = len(floor_widths) - 1
        rest_floor = last_floor - 1

        # A SECOND REST, MID-SEGMENT, ONCE SEGMENTS GOT LONG.
        #
        # Segments were 8-11 floors with one campfire before the boss.
        # They are now 12-16 (fewer bosses, longer roads) and that single
        # rest stopped being enough: measured on bench_roles, the longer
        # run dropped Abyssnia's clear rate 28% -> 25% and Voidcrest's
        # 52% -> 45%, and -- the part that actually matters -- pushed
        # "double support" clear of "1 of each" in Voidcrest by more than
        # the benchmark's noise floor for the first time in a long while.
        #
        # That is what unrelieved attrition does: it stops rewarding the
        # comp that fights well and starts rewarding the comp that simply
        # outlasts, which collapses the roster back onto one answer. More
        # floors need proportionally more rest, so segments long enough to
        # need it get a campfire near the midpoint.
        mid_rest_floor = mid_rest_floor_for(len(floor_widths))

        # Middle floors are every floor strictly between start and rest floor.
        middle_floor_indices = list(range(1, rest_floor))
        thirds = max(1, len(middle_floor_indices) // 3)

        def stage_for_floor(floor: int) -> str:
            position = middle_floor_indices.index(floor) if floor in middle_floor_indices else 0
            if position < thirds:
                return "early"
            if position < thirds * 2:
                return "mid"
            return "late"

        # MAX_PER_RUN MEANS PER RUN, and for a long time it did not.
        #
        # This dict used to be created fresh here, and this function runs
        # once per boss SEGMENT -- so a run with four segments enforced
        # every cap four times over. Measured across 40 runs: Secret is
        # capped at 1 and appeared 3 times; Merchant is capped at 2 and
        # appeared 8. The constant is literally named MAX_PER_RUN and had
        # never once been a per-run cap.
        #
        # Passing the caller's dict in threads one tally through the whole
        # run. It defaults to a fresh dict so a single segment generated
        # on its own (tests, tools) still behaves sensibly.
        counts: dict[RoomType, int] = run_counts if run_counts is not None else {}
        room_types: dict[str, RoomType] = {}

        # Sort nodes by floor so per-run caps fill up in a stable, readable order.
        for node_id in sorted(nodes, key=lambda n: self._parse_id(n)):
            floor, _ = self._parse_id(node_id)

            if floor == 0:
                room_types[node_id] = RoomType.START
                continue
            if floor == last_floor:
                room_types[node_id] = RoomType.BOSS
                continue
            if floor == rest_floor or floor == mid_rest_floor:
                room_types[node_id] = RoomType.CAMPFIRE
                continue

            room_types[node_id] = self._roll_room_type(
                stage_for_floor(floor), floor, counts
            )

        return room_types

    def _roll_room_type(
        self, stage: str, floor: int, counts: dict[RoomType, int]
    ) -> RoomType:
        weights = dict(ROOM_WEIGHTS_BY_STAGE[stage])

        if floor < ELITE_MIN_FLOOR_INDEX:
            weights.pop(RoomType.ELITE, None)

        for room_type, cap in MAX_PER_RUN.items():
            if counts.get(room_type, 0) >= cap:
                weights.pop(room_type, None)

        if not weights:
            weights = {RoomType.COMBAT: 1}

        room_type = self.rng.choices(
            list(weights.keys()), weights=list(weights.values()), k=1
        )[0]
        counts[room_type] = counts.get(room_type, 0) + 1
        return room_type

    # ------------------------------------------------------------------
    # Node id helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_id(floor: int, index: int) -> str:
        return f"{floor}_{index}"

    @staticmethod
    def _parse_id(node_id: str) -> tuple[int, int]:
        floor_str, index_str = node_id.split("_")
        return int(floor_str), int(index_str)
