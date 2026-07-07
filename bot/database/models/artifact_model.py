"""
Artifacts are a distinct system from regular equipment: instead of flat stat
substats, each one carries a unique gameplay-altering effect (e.g. "Blood
Pendant: -10 HP, +30 Attack" or "Ancient Tome: every 3rd spell costs 0 mana").

ArtifactTemplate is the hand-authored catalog entry (name, description,
effect definition). PlayerArtifact is a permanent, owned copy -- artifacts
don't get re-rolled with substats the way equipment does, so no separate
"instance" fields are needed beyond ownership + timestamp.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base
from bot.database.models.enums import Rarity


class ArtifactTemplate(Base):
    __tablename__ = "artifact_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(256))
    rarity: Mapped[Rarity] = mapped_column(default=Rarity.RARE)

    # e.g. {"kind": "on_hit_lifesteal", "percent": 10}
    # The combat/loot systems interpret `effect` by `kind`.
    effect: Mapped[dict] = mapped_column(JSON, default=dict)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ArtifactTemplate {self.name!r}>"


class PlayerArtifact(Base):
    __tablename__ = "player_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("artifact_templates.id")
    )
    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="artifacts")  # noqa: F821
    template: Mapped["ArtifactTemplate"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerArtifact template_id={self.template_id}>"
