"""
Quests: two kinds, sharing one table (distinguished by `kind`).

BEGINNER quests (kind="beginner") are seeded once per player, all at once,
the first time they touch the quest system (see
bot/services/quest_service.py::ensure_beginner_quests_seeded) -- one row
per entry in bot/game/economy/quest_config.py::BEGINNER_QUESTS. Each can
only ever be completed once; completing all of them grants a one-time
bonus (Player.beginner_quest_bonus_claimed guards against granting that
bonus twice).

BASIC quests (kind="basic") are the repeating side: at most one active row
per player at a time, replaced whenever a new one is rolled (gated by
Player.last_basic_quest_assigned_at, a 5-hour cooldown -- see
quest_service.roll_basic_quest). Completed basic quest rows are left in
place as history rather than deleted; they just stop being "active".

Both kinds share the same progress-tracking mechanism: `goal_type` is a
string key (e.g. "win_battles", "upgrade_gear") that
quest_service.record_progress() call sites throughout the bot report
progress against; `progress` increments (or is set, for milestone-style
goals) until it reaches `goal_count`, at which point the quest is marked
completed and its reward is granted immediately (no separate "claim" step
-- see quest_config for each quest's reward dict).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base


class PlayerQuest(Base):
    __tablename__ = "player_quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )

    quest_id: Mapped[str] = mapped_column(String(64))  # key into quest_config's pools
    kind: Mapped[str] = mapped_column(String(16))       # "basic" or "beginner"
    goal_type: Mapped[str] = mapped_column(String(32))
    # Snapshotted from quest_config at assignment time (not looked up live)
    # so an in-progress quest doesn't shift under the player if the config
    # is retuned later.
    goal_count: Mapped[int] = mapped_column(Integer)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    assigned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    player: Mapped["Player"] = relationship(back_populates="quests")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PlayerQuest id={self.id} quest_id={self.quest_id!r} kind={self.kind} "
            f"progress={self.progress}/{self.goal_count} completed={self.is_completed}>"
        )
