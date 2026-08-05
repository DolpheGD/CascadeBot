"""
Which players have actually played in which guilds.

WHY THIS EXISTS. Leaderboards are per-server, and the original design
scoped them by reading `guild.members` from Discord's member cache --
deliberately, to avoid a schema change. That cache is only populated if
the bot requests the **privileged `members` intent**, and this bot
requests `Intents.default()`, which does not include it (see
bot/client.py, which avoids privileged intents on purpose).

So `guild.members` came back with nothing usable, the "fall back to just
the caller" branch fired every single time, and every leaderboard in
every server showed exactly one player: whoever ran the command. The
feature had never worked.

The fix is to stop asking Discord who's in the server and record it
ourselves. A row here means "this player has used the bot in this
guild", which is a better definition for a leaderboard anyway -- it ranks
people who actually play here, not everyone who happens to be in the
server and has never touched the bot.

Rows are upserted from a single `on_interaction` listener, so every
command, button and select keeps it current with no per-cog bookkeeping.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models.base_model import Base


class PlayerGuild(Base):
    """One row per (player, guild) the player has been seen playing in."""

    __tablename__ = "player_guilds"
    __table_args__ = (
        UniqueConstraint("player_id", "guild_id", name="uq_player_guild"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Not a ForeignKey to players.id on purpose: the listener records a
    # sighting for any interaction, including from someone who hasn't run
    # /start yet. A sighting is about a Discord user, not about a Player
    # row that may not exist; the leaderboard join filters to real
    # players anyway.
    player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)

    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerGuild player={self.player_id} guild={self.guild_id}>"
