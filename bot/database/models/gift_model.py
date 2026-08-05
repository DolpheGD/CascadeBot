"""
Player-to-player gift packages.

A gift is a ROW, not a transfer. The sender's resources are debited when
they send and the package sits here until the recipient collects it --
which matters for three reasons:

  1. The recipient may not exist yet as a Player. Gifting someone who
     hasn't run /start should work; they collect when they join.
  2. It gives the recipient a moment of agency. A silent balance change
     is indistinguishable from a bug.
  3. It makes the whole thing auditable. Every gift ever sent is a row
     with a sender, a recipient, contents and timestamps, so "where did
     my resources go" always has an answer.

Nothing is ever deleted on collection -- `collected_at` is stamped
instead. A gift log you can't read after the fact isn't a log.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base

if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.player_model import Player


class Gift(Base):
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    # NOT a foreign key: you can gift someone who has never played, and
    # they collect it when they do. A FK would make that impossible for
    # no benefit -- the id is a Discord user id either way.
    recipient_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # {currency: amount}. Reassigned wholesale on any change, never
    # mutated in place -- SQLAlchemy doesn't track mutation of a plain
    # JSON column.
    contents: Mapped[dict] = mapped_column(JSON, default=dict)

    # Optional one-line note from the sender. Sanitised at send time (see
    # gift_service.MESSAGE_PATTERN) -- it's player text rendered into an
    # embed, so it can't be allowed to carry markdown or pings.
    note: Mapped[str | None] = mapped_column(String(140), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    collected_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sender: Mapped["Player"] = relationship(foreign_keys=[sender_id])

    def is_collected(self) -> bool:
        return self.collected_at is not None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Gift {self.id} {self.sender_id}->{self.recipient_id} {self.contents}>"
