"""
The Dojo -- player-authored challenges.

This is the only place in the game where one player's content is shown to
another, and that single fact drives most of the design below.

WHY THE ENEMY SET IS STORED AS NAMES, NOT AS A SNAPSHOT.

The obvious design is to freeze the enemies' stats into the row so a
challenge always fights exactly what its author saw. It is also the wrong
one here: a frozen snapshot is a second copy of the enemy roster that
nobody maintains, so the day an enemy is retuned every published
challenge silently keeps the old numbers, and the game now has two
answers to "how strong is a Coolant Wraith".

Storing names means a challenge is a RECIPE, resolved against the live
roster every time it is played. A retune moves every challenge with it,
and an enemy that is removed makes its challenges refuse to start rather
than fighting a ghost -- see dojo_service.resolve_enemies.

WHY CLEARS ARE THEIR OWN TABLE.

`DojoClear` exists so the per-player relationship (have I beaten this,
when, how many times) is separate from the challenge itself. Counting
clears on the challenge row alone would answer "how popular is this" and
nothing else; the per-player row is what lets the UI say "you have
already beaten this" and what a leaderboard would need later.

MODERATION IS A COLUMN, not a deletion. `published` going false is how a
challenge is taken down -- by its author, or by the bot owner. Deleting
the row instead would break every DojoClear pointing at it and erase the
evidence of whatever got it removed.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class DojoChallenge(Base):
    """One player-authored encounter."""

    __tablename__ = "dojo_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True)

    # Player-authored text. Length-capped here AND pattern-checked in the
    # service -- the column limit is the last line of defence, not the
    # first, because a database truncation is a silent corruption where a
    # service rejection is a message the author can act on.
    name: Mapped[str] = mapped_column(String(48))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # The recipe: [{"enemy": "Coolant Wraith", "count": 2}, ...]
    # Resolved against the live roster at play time. See the module note.
    enemies: Mapped[list] = mapped_column(JSON, default=list)
    level: Mapped[int] = mapped_column(Integer, default=20)

    # Published challenges are listed and playable by anyone. Unpublished
    # ones are the author's drafts and are visible only to them.
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Short, human-typeable, unique. Case is normalised on lookup so
    # nobody has to care whether they were sent A1B2C3 or a1b2c3.
    share_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)

    # Aggregates for the browse list. Denormalised on purpose: the list
    # shows a clear rate for every row, and computing that from DojoClear
    # per row would be a query per entry on every page turn.
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    clears: Mapped[int] = mapped_column(Integer, default=0)

    # Set when the bot owner takes something down, so a removal can be
    # told apart from an author unpublishing their own draft.
    removed_by_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    author: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DojoChallenge {self.share_code} {self.name!r} by {self.author_id}>"


class DojoClear(Base):
    """One player's history with one challenge."""

    __tablename__ = "dojo_clears"
    __table_args__ = (
        UniqueConstraint("player_id", "challenge_id", name="uq_dojo_clear"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dojo_challenges.id", ondelete="CASCADE"), index=True)

    times_cleared: Mapped[int] = mapped_column(Integer, default=0)
    first_cleared_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_cleared_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
