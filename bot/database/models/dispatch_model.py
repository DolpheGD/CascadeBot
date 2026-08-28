"""
Dispatch board rows: which contracts a player has out, and who is on them.

The assigned character ids live in a JSON column rather than a join
table. That is the right call HERE and would not be elsewhere: a dispatch
is a short-lived, whole-object record that is always read in full and
never queried by member ("which contracts is Josh on" is answered by
scanning a player's three-or-fewer active rows, not by an index). A join
table would add a second table and a cascade to maintain for a list that
is at most four integers long.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, ForeignKey,
                        Integer, String, func)
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models.base_model import Base


class PlayerDispatch(Base):
    """One contract, out or waiting to be claimed.

    Rows are DELETED on claim rather than kept as history. The board is a
    working list, and an audit trail of every timber run anybody has ever
    done is a table that grows forever to answer a question nobody asks.
    """

    __tablename__ = "player_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )

    contract_id: Mapped[str] = mapped_column(String(48))

    # PlayerCharacter ids, not template ids. The distinction matters:
    # two copies of the same character are two separate rows and only one
    # of them is away.
    # Reassigned wholesale by the service, never mutated in place --
    # SQLAlchemy does not detect in-place mutation of a plain JSON
    # column, the same trap story_service.set_flags documents.
    character_ids: Mapped[list] = mapped_column(JSON, default=list)

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Stored rather than derived from started_at + hours, so that
    # rebalancing a contract's duration never retroactively moves a
    # dispatch somebody already sent out.
    ends_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    # The fit multiplier at the moment of sending, frozen. Recomputing it
    # on claim would let a player send a bad team, level them while the
    # contract runs, and collect on a team that never went.
    fit: Mapped[int] = mapped_column(Integer, default=100)   # percent

    claimed: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<PlayerDispatch {self.contract_id!r} "
                f"members={len(self.character_ids or [])}>")
