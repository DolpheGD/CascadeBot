"""
Shared banner plumbing: pull history, and the pity maths both banners use.

The character banner and the Character Card banner are deliberately the
same machine with different content. Before this module they were two
separate implementations that had already drifted -- characters had a
soft-pity ramp and cards did not, so the two banners advertised "the same
system" while behaving differently in the one place a player would
actually notice.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.pull_model import PullRecord

# How many results each banner remembers, per player. 100 is the number
# the player asked for and is also about where the display stops being
# useful -- twenty pages of history is an archive, not an answer.
HISTORY_LIMIT = 100

BANNERS = ("character", "card")


def record_pull(db, player, banner: str, name: str, star_rating: int,
                was_pity: bool = False) -> None:
    """Append one result, then trim that banner back to HISTORY_LIMIT.

    Trimming here rather than on read keeps the table bounded whatever
    happens upstream -- a read-side limit would still let the row count
    grow forever, and this table has no other reason to be large.
    """
    db.add(PullRecord(
        player_id=player.id, banner=banner, name=name,
        star_rating=star_rating, was_pity=bool(was_pity),
        pulled_at=dt.datetime.now(dt.timezone.utc),
    ))
    db.flush()

    surplus = (
        db.query(PullRecord)
        .filter_by(player_id=player.id, banner=banner)
        .order_by(PullRecord.id.desc())
        .offset(HISTORY_LIMIT)
        .all()
    )
    for row in surplus:
        db.delete(row)


def history(db, player_id: int, banner: str, limit: int = HISTORY_LIMIT) -> list[PullRecord]:
    """Most recent first."""
    return (
        db.query(PullRecord)
        .filter_by(player_id=player_id, banner=banner)
        .order_by(PullRecord.id.desc())
        .limit(limit)
        .all()
    )


def soft_pity_rate(base_percent: float, pulls_since: int,
                   soft_start: int, step: float) -> float:
    """The 5-star chance for the NEXT pull, with the soft-pity ramp.

    Flat at `base_percent` until `soft_start`, then +`step` points per
    pull. Shared by both banners so a change to how pity feels lands on
    both at once -- which is the entire reason this is here and not
    duplicated in two configs.
    """
    into_soft = (pulls_since + 1) - soft_start
    if into_soft <= 0:
        return base_percent
    return min(100.0, base_percent + into_soft * step)
