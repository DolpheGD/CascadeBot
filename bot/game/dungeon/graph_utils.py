"""
Read/write helpers for a dungeon graph dict (the shape produced by
DungeonGenerator.generate() and stored on Expedition.graph). Kept separate
from the generator so combat/cogs can navigate a run without importing
generation logic.
"""

from __future__ import annotations


def get_node(graph: dict, node_id: str) -> dict:
    try:
        return graph["nodes"][node_id]
    except KeyError as exc:
        raise ValueError(f"No such node: {node_id}") from exc


def get_available_moves(graph: dict, current_node_id: str) -> list[str]:
    """Node ids the player can move to next from `current_node_id`."""
    return list(get_node(graph, current_node_id)["edges"])


def is_valid_move(graph: dict, current_node_id: str, target_node_id: str) -> bool:
    return target_node_id in get_available_moves(graph, current_node_id)


def mark_completed(graph: dict, node_id: str) -> None:
    get_node(graph, node_id)["completed"] = True


def is_boss_defeated(graph: dict) -> bool:
    return get_node(graph, graph["boss_node"])["completed"]


def nodes_of_type(graph: dict, room_type: str) -> list[str]:
    return [nid for nid, n in graph["nodes"].items() if n["room_type"] == room_type]


def floor_of(graph: dict, node_id: str) -> int:
    return get_node(graph, node_id)["floor"]


def render_ascii(graph: dict) -> str:
    """Quick debug visualization: one line per floor, room-type initials."""
    by_floor: dict[int, list[str]] = {}
    for node_id, node in graph["nodes"].items():
        by_floor.setdefault(node["floor"], []).append(
            f"{node_id}:{node['room_type'][:4]}"
        )

    lines = []
    for floor in sorted(by_floor):
        lines.append(f"Floor {floor}: " + "  ".join(sorted(by_floor[floor])))
    return "\n".join(lines)
