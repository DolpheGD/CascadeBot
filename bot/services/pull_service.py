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


# ======================================================================
# TARGETED 5-STARS ("pick-up")
# ======================================================================
#
# The player nominates one 5-star. It then gets a boosted share of every
# 5-star that banner produces, and -- the part that actually matters --
# missing is SELF-CORRECTING: a 5-star that is not the target arms a
# guarantee, so the NEXT 5-star is the target no matter what.
#
# The worst case is therefore exactly two 5-stars, and a player can plan
# around that. Without the guarantee, targeting is just a rate change and
# an unlucky player can miss six times in a row while being told the
# system is helping them.
#
# ONE IMPLEMENTATION, BOTH BANNERS. Characters and cards keep separate
# targets and separate guarantee flags, but the RULE lives here. The two
# banners already have near-duplicate pity code that has drifted once;
# a second copy of the targeting rule would drift the same way, and the
# symptom would be "my guarantee worked on characters but not on cards",
# which is indistinguishable from bad luck and would never get reported.

# The target's share of 5-star pulls when a target is set and no
# guarantee is armed. 55% rather than 50 because a coin flip that the
# player deliberately opted into should feel slightly generous; combined
# with the guarantee this makes the expected number of 5-stars needed to
# land a specific character about 1.45.
TARGET_FIVE_STAR_RATE_PERCENT = 55.0


def resolve_five_star(rng, pool: list, target_key, key_of, guaranteed: bool):
    """Choose which 5-star a pull produces.

    `pool`       every 5-star that can be pulled
    `target_key` the player's nominated target, or None
    `key_of`     callable mapping a pool entry to the key `target_key`
                 uses -- a template name for characters, a card id for
                 cards, which is why this is a parameter and not an
                 attribute lookup
    `guaranteed` whether a previous miss armed the guarantee

    Returns (chosen, hit_target, guarantee_after).
    """
    if not pool:
        return None, False, guaranteed

    target = next((entry for entry in pool if key_of(entry) == target_key), None)
    if target is None:
        # No target set, or the target is not currently pullable. Either
        # way this is an ordinary 5-star and the guarantee is untouched --
        # NOT consumed. Consuming it here would silently spend a
        # guarantee the player earned, on a banner where their target
        # could not appear.
        return rng.choice(pool), False, guaranteed

    if guaranteed:
        return target, True, False

    if rng.random() * 100 < TARGET_FIVE_STAR_RATE_PERCENT:
        return target, True, False

    # A miss. Pick from everything EXCEPT the target -- rolling the whole
    # pool here would let the "miss" branch return the target anyway,
    # which makes the measured target rate higher than the advertised one
    # and the guarantee arm itself after a pull the player counts as a
    # win.
    others = [entry for entry in pool if key_of(entry) != target_key]
    return (rng.choice(others) if others else target), False, True
