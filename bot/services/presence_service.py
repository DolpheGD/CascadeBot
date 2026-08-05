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
