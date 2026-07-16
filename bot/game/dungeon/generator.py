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
    MAX_PER_RUN,
    REST_FLOOR_WIDTH,
    ROOM_WEIGHTS_BY_STAGE,
    SEGMENT_FLOOR_RANGE,
    roll_num_regular_bosses,
)


class DungeonGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    def generate(
        self,
        region: str,
        num_floors: int | None = None,
        num_bosses: int | None = None,
        num_paths: int = 10,
        min_width: int = 3,
        max_width: int = 5,
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

        for seg_index, seg_floors in enumerate(segment_lengths):
            if seg_floors < 4:
                raise ValueError("each boss segment needs at least 4 floors")

            segment = self._generate_segment(seg_floors, num_paths, min_width, max_width)

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
        self, num_floors: int, num_paths: int, min_width: int, max_width: int
    ) -> dict[str, dict]:
        floor_widths = self._build_floor_widths(num_floors, min_width, max_width)
        nodes, edges = self._walk_paths(floor_widths, num_paths)
        edges = self._densify_edges(floor_widths, nodes, edges, target=3)
        room_types = self._assign_room_types(floor_widths, nodes)

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
        return widths

    # ------------------------------------------------------------------
    # Path walking -> nodes & edges
    # ------------------------------------------------------------------
    def _walk_paths(
        self, floor_widths: list[int], num_paths: int
    ) -> tuple[set[str], dict[str, set[str]]]:
        nodes: set[str] = {self._make_id(0, 0)}
        edges: dict[str, set[str]] = {}

        for _ in range(num_paths):
            idx = 0
            for floor in range(len(floor_widths) - 1):
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
    # Edge densification -- "each floor should have more options than
    # just 2." The raw random walk above guarantees every node is
    # reachable, but often leaves individual nodes with only 1-2 outgoing
    # edges. This pass tops every node up to `target` outgoing edges by
    # connecting it to its nearest-by-index EXISTING next-floor nodes
    # (never inventing new nodes, so reachability/serialization stay
    # untouched) -- so standing at a node usually means 3 real paths
    # forward, not 1.
    # ------------------------------------------------------------------
    def _densify_edges(
        self, floor_widths: list[int], nodes: set[str], edges: dict[str, set[str]], target: int = 3
    ) -> dict[str, set[str]]:
        nodes_by_floor: dict[int, list[int]] = {}
        for node_id in nodes:
            floor, index = self._parse_id(node_id)
            nodes_by_floor.setdefault(floor, []).append(index)
        for floor in nodes_by_floor:
            nodes_by_floor[floor].sort()

        last_floor = len(floor_widths) - 1

        for floor in range(last_floor):
            next_indices = nodes_by_floor.get(floor + 1, [])
            if not next_indices:
                continue

            for idx in nodes_by_floor.get(floor, []):
                node_id = self._make_id(floor, idx)
                current = edges.setdefault(node_id, set())
                cap = min(target, len(next_indices))
                if len(current) >= cap:
                    continue

                candidates = sorted(next_indices, key=lambda ni: (abs(ni - idx), ni))
                for next_idx in candidates:
                    if len(current) >= cap:
                        break
                    current.add(self._make_id(floor + 1, next_idx))

        return edges

    # ------------------------------------------------------------------
    # Room type assignment
    # ------------------------------------------------------------------
    def _assign_room_types(
        self, floor_widths: list[int], nodes: set[str]
    ) -> dict[str, RoomType]:
        last_floor = len(floor_widths) - 1
        rest_floor = last_floor - 1
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

        counts: dict[RoomType, int] = {}
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
            if floor == rest_floor:
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
