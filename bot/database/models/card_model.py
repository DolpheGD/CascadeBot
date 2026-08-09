"""
Character Cards -- one powerful, levellable slot per character.

Deliberately NOT an InventoryItem with a seventh EquipmentSlot value.
That was the first design and it was wrong for three reasons, each of
which would have leaked into a dozen call sites:

  * every existing inventory query, sort, sell, forge and mass-sell path
    filters on InventoryItem and would have needed a "...but not cards"
    clause. Miss one and a player mass-sells their best Card by rarity.
  * Cards have no substats and no rerolls, so most of InventoryItem's
    columns would sit permanently null.
  * Cards level to 100 against gear's 35, on a different curve, with a
    different currency.

Two tables, mirroring the character pattern (CharacterTemplate ->
PlayerCharacter):

    CardTemplate   the catalog row, upserted from card_config on startup
    PlayerCard     one owned copy, with its own level and equipped state
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base


class CardTemplate(Base):
    __tablename__ = "card_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    star_rating: Mapped[int] = mapped_column(Integer, default=3)
    lore: Mapped[str] = mapped_column(String(512), default="")

    # The three main stats, stored as a JSON-ish string map. Kept as a
    # column rather than three (stat, value) pairs because the set of
    # stats varies per card and a fixed triple of columns would encode
    # "always exactly three" into the schema, which is a design decision
    # rather than a storage one.
    stats_json: Mapped[str] = mapped_column(String(256), default="{}")

    ability_id: Mapped[str] = mapped_column(String(64), default="")
    ability_pool: Mapped[str] = mapped_column(String(16), default="artifact")


class PlayerCard(Base):
    __tablename__ = "player_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("card_templates.id"))

    level: Mapped[int] = mapped_column(Integer, default=1)

    # Which character is wearing it, or NULL. One card per character is
    # enforced in the service rather than by a unique constraint: the
    # constraint would also forbid two UNEQUIPPED cards (both NULL) on
    # SQLite in some configurations, and the service has to give a
    # readable refusal anyway.
    character_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("player_characters.id"), nullable=True, index=True
    )

    template: Mapped["CardTemplate"] = relationship(lazy="joined")

    @property
    def display_name(self) -> str:
        return self.template.name if self.template else "Unknown Card"
