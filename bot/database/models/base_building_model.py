"""
The two base buildings that replaced the mailbox: the Research Lab and
the Forge.

Both are ONE row per player (like PlayerMailbox was) rather than an
own-a-copy-of-a-template catalog (like harvesters and shrines), because
there is only ever one of each -- what varies is its level and, for the
Lab, which projects have been finished.

PlayerResearch is the interesting one: it's a row per (player, project)
rather than a JSON blob on PlayerLab, so a project's state is queryable
("which projects are running right now", "has this player finished
X") without deserialising anything, and adding a project to the catalog
needs no migration.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class PlayerLab(Base):
    """The Research Lab building itself. Level gates which projects are
    available, how many can run at once, and how fast they finish."""

    __tablename__ = "player_labs"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerLab player={self.player_id} lvl={self.level}>"


class PlayerResearch(Base):
    """One player's state for one research project.

    A row exists only once the project has been STARTED. `completed_at`
    is NULL while it's still running and set when collected -- so
    "in progress" and "done" are the same table, distinguished by one
    nullable column rather than a status string that could drift.
    """

    __tablename__ = "player_research"
    __table_args__ = (
        UniqueConstraint("player_id", "project_id", name="uq_player_research"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(String(64), index=True)

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # When the research finishes and can be collected. Stored rather than
    # recomputed because the lab's speed multiplier can change (an
    # upgrade mid-project shouldn't retroactively rewrite a timer the
    # player has already been waiting on).
    finishes_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        state = "done" if self.completed_at else "running"
        return f"<PlayerResearch {self.project_id!r} {state}>"


class PlayerForge(Base):
    """The Forge building. Level gates the maximum rarity it can produce
    and unlocks its more advanced operations (reforge, ability transfer)."""

    __tablename__ = "player_forges"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)

    player: Mapped["Player"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerForge player={self.player_id} lvl={self.level}>"
