"""
Server leaderboards -- the lightweight half of the multiplayer layer.

A raid is the cooperative side; this is the comparative one. Both exist
for the same reason: until now nothing in CascadeBot ever told a player
that anyone else was playing it.

SCOPE. Boards are ranked across every registered Player, then FILTERED to
the Discord members present in the guild the command was run in (the cog
passes those ids in). Ranking globally and filtering locally, rather than
storing a guild id on Player, keeps the feature entirely read-only -- no
schema change, nothing to backfill, and a player who's in two servers
appears correctly on both boards without any bookkeeping.

WHAT'S MEASURED. Four boards, chosen because each rewards a different
thing and no single player is likely to top all four:

  * Squad Power   -- the sum of the four active squad members' levels.
                     "How strong is the team you actually field."
  * Roster        -- total levels across every owned character. Rewards
                     breadth, and is the same measure the domain and raid
                     unlocks use, so it's a number players already track.
  * Deepest Clear -- highest-tier region fully cleared. Rewards skill and
                     progression rather than time spent.
  * Collection    -- distinct characters owned. Rewards the gacha side.

Everything is computed on demand. There is no cached leaderboard table,
because a board that can go stale is a board that will, and at the scale
a Discord bot operates on (hundreds of rows, not millions) the query is
cheap enough that caching would cost more correctness than it buys
performance.
"""

from __future__ import annotations

from sqlalchemy import func

from bot.database.models.character_model import PlayerCharacter, SquadSlot
from bot.database.models.enums import ExpeditionStatus
from bot.database.models.expedition_model import Expedition
from bot.database.models.player_model import Player
from bot.game.dungeon.region_config import REGION_DIFFICULTY, ordered_regions

BOARDS = [
    ("squad_power", "⚔️ Squad Power", "Combined level of your 4 active squad members"),
    ("roster", "📚 Roster Levels", "Total levels across every character you own"),
    ("deepest", "🏔️ Deepest Clear", "Highest-tier region you've fully cleared"),
    ("collection", "🎴 Collection", "Distinct characters owned"),
]

DEFAULT_BOARD = "squad_power"
TOP_N = 10


def _name_map(db, player_ids: list[int]) -> dict[int, str]:
    if not player_ids:
        return {}
    rows = db.query(Player.id, Player.username).filter(Player.id.in_(player_ids)).all()
    return {pid: name for pid, name in rows}


def _squad_power(db, member_ids: list[int]) -> list[tuple[int, int]]:
    """(player_id, summed level of squad members). Joins through
    SquadSlot so only characters actually FIELDED count -- otherwise this
    would be a duplicate of the roster board."""
    rows = (
        db.query(SquadSlot.player_id, func.sum(PlayerCharacter.level))
        .join(PlayerCharacter, SquadSlot.character_id == PlayerCharacter.id)
        .filter(SquadSlot.player_id.in_(member_ids))
        .group_by(SquadSlot.player_id)
        .all()
    )
    return [(pid, int(total or 0)) for pid, total in rows]


def _roster_levels(db, member_ids: list[int]) -> list[tuple[int, int]]:
    rows = (
        db.query(PlayerCharacter.player_id, func.sum(PlayerCharacter.level))
        .filter(PlayerCharacter.player_id.in_(member_ids))
        .group_by(PlayerCharacter.player_id)
        .all()
    )
    return [(pid, int(total or 0)) for pid, total in rows]


def _collection(db, member_ids: list[int]) -> list[tuple[int, int]]:
    rows = (
        db.query(PlayerCharacter.player_id, func.count(PlayerCharacter.id))
        .filter(PlayerCharacter.player_id.in_(member_ids))
        .group_by(PlayerCharacter.player_id)
        .all()
    )
    return [(pid, int(total or 0)) for pid, total in rows]


def _deepest_clear(db, member_ids: list[int]) -> list[tuple[int, int]]:
    """(player_id, tier of the hardest region they've COMPLETED). Scored
    by region tier rather than by clear count, so grinding the easiest
    region a hundred times never outranks one genuine Abyssnia clear."""
    rows = (
        db.query(Expedition.player_id, Expedition.region)
        .filter(
            Expedition.player_id.in_(member_ids),
            Expedition.status == ExpeditionStatus.COMPLETED,
        )
        .distinct()
        .all()
    )
    best: dict[int, int] = {}
    for pid, region in rows:
        tier = REGION_DIFFICULTY.get(region, {}).get("tier", 0)
        best[pid] = max(best.get(pid, 0), tier)
    return list(best.items())


_BOARD_QUERIES = {
    "squad_power": _squad_power,
    "roster": _roster_levels,
    "collection": _collection,
    "deepest": _deepest_clear,
}


def _format_value(board: str, value: int) -> str:
    if board == "deepest":
        regions = ordered_regions()
        if 1 <= value <= len(regions):
            # tiers are 1-based and ordered_regions() is easiest-first
            return regions[value - 1]
        return "None yet"
    if board == "collection":
        return f"{value} character{'s' if value != 1 else ''}"
    return f"Lv. {value}"


def get_board(db, board: str, member_ids: list[int], viewer_id: int | None = None) -> dict:
    """Ranked entries for one board, restricted to `member_ids` (the
    Discord users actually in this server -- see the SCOPE note in the
    module docstring).

    Returns {"entries": [...], "viewer_rank": int|None, "viewer_entry":
    dict|None}. The viewer is surfaced separately so someone outside the
    top 10 still learns where they stand, which is the only thing that
    makes a leaderboard motivating rather than discouraging."""
    query = _BOARD_QUERIES.get(board) or _BOARD_QUERIES[DEFAULT_BOARD]
    pairs = [(pid, value) for pid, value in query(db, member_ids) if value > 0]
    pairs.sort(key=lambda pair: (-pair[1], pair[0]))

    names = _name_map(db, [pid for pid, _ in pairs])
    entries = [
        {
            "rank": i + 1,
            "player_id": pid,
            "name": names.get(pid, "Unknown"),
            "value": value,
            "display": _format_value(board, value),
        }
        for i, (pid, value) in enumerate(pairs)
    ]

    viewer_entry = next((e for e in entries if e["player_id"] == viewer_id), None)
    return {
        "board": board,
        "entries": entries[:TOP_N],
        "total_ranked": len(entries),
        "viewer_rank": viewer_entry["rank"] if viewer_entry else None,
        "viewer_entry": viewer_entry,
    }
