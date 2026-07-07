"""
Generates the per-expedition dungeon graph stored in Expedition.graph.

Approach (same family as Slay the Spire's map generation): walk several
random paths from the start floor to the boss floor, letting each path drift
left/right by at most one node per floor. The union of every path's nodes
and edges becomes the graph -- this guarantees every node is reachable from
start and the boss is reachable from every node, without needing a separate
connectivity-repair pass.

Room types are assigned afterward: START/BOSS are fixed, the floor
immediately before the boss is forced to be all CAMPFIRE (so the player can
always heal up before the fight), and everything else is weighted-random per
room_config.py, subject to per-run caps and the "no elite too early" rule.

Output shape (JSON-serializable, matches Expedition.graph):

    {
        "region": "Whispering Forest",
        "num_floors": 9,
        "start_node": "0_0",
        "boss_node": "8_0",
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
)


class DungeonGenerator:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    def generate(
        self,
        region: str,
        num_floors: int = 9,
        num_paths: int = 6,
        min_width: int = 2,
        max_width: int = 4,
    ) -> dict:
        if num_floors < 4:
            raise ValueError("num_floors must be at least 4 (start, >=1 middle, rest, boss)")

        floor_widths = self._build_floor_widths(num_floors, min_width, max_width)
        nodes, edges = self._walk_paths(floor_widths, num_paths)
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

        return {
            "region": region,
            "num_floors": num_floors,
            "start_node": self._make_id(0, 0),
            "boss_node": self._make_id(num_floors - 1, 0),
            "nodes": node_data,
        }

    # ------------------------------------------------------------------
    # Floor layout
    # ------------------------------------------------------------------
    def _build_floor_widths(self, num_floors: int, min_width: int, max_width: int) -> list[int]:
        widths = [1]  # floor 0: start
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
