"""
Recording and reading which players play in which guild.

See bot/database/models/presence_model.py for why this exists at all --
short version: leaderboards were scoped off Discord's member cache, which
is empty without a privileged intent the bot doesn't request, so every
board showed only the person who ran the command.
"""

from __future__ import annotations

from bot.database.models.presence_model import PlayerGuild
from bot.utils.time_utils import utcnow


def record_seen(db, player_id: int, guild_id: int | None) -> None:
    """Note that `player_id` is playing in `guild_id`.

    Called from the global interaction listener, so it runs on every
    button press in the game and has to be cheap and never raise: a
    failure here must not break the interaction the player actually
    wanted. DMs (guild_id None) are skipped -- there's no board to be on.
    """
    if guild_id is None:
        return
    row = (
        db.query(PlayerGuild)
        .filter_by(player_id=player_id, guild_id=guild_id)
        .first()
    )
    if row is None:
        db.add(PlayerGuild(player_id=player_id, guild_id=guild_id, last_seen_at=utcnow()))
    else:
        row.last_seen_at = utcnow()
    db.commit()


def touch_last_seen(db, player_id: int) -> None:
    """Keep Player.last_seen_at current -- but never close a long gap.

    A SHORT gap is advanced normally, so an active player's timestamp
    tracks them. A gap long enough to be worth reporting is LEFT ALONE,
    because this runs from on_interaction, which fires before the command
    handler does: overwriting it here would destroy the reading the
    welcome-back summary exists to take, and it would do so on every
    single interaction, so the summary would never appear at all.

    The stamp past a long gap is advanced by away_service.mark_shown(),
    once the player has actually been told. That also means the summary
    survives a player running a command that does not render it.
    """
    from bot.database.models.player_model import Player
    from bot.services.away_service import MIN_AWAY

    player = db.query(Player).filter_by(id=player_id).one_or_none()
    if player is None:
        return
    now = utcnow()
    previous = player.last_seen_at
    if previous is not None:
        from bot.utils.time_utils import as_utc
        if (now - as_utc(previous)) >= MIN_AWAY:
            return  # a summary is owed; leave the evidence in place
    player.last_seen_at = now
    db.commit()


def player_ids_in_guild(db, guild_id: int, include: int | None = None) -> list[int]:
    """Everyone recorded as playing in this guild.

    `include` is added unconditionally -- normally the caller, so a player
    whose first ever action is `/leaderboard` still appears on it rather
    than seeing an empty board because the listener hadn't committed
    their row yet."""
    ids = {
        row.player_id
        for row in db.query(PlayerGuild.player_id).filter_by(guild_id=guild_id).all()
    }
    if include is not None:
        ids.add(include)
    return list(ids)
