"""
Characters -- the core of the Combat Overhaul.

The gacha now pulls CHARACTERS, not gear (see bot/game/economy/gacha_config.py
and bot/services/character_gacha_service.py). Every character -- including your own
avatar -- is a full combatant with its own level, equipment (4 slots: weapon,
artifact, armor, accessory), a set character skill (mana cost), and a set
ultimate (energy cost). You bring a squad of 4 into every expedition/battle.

    CharacterTemplate  -- hand-authored catalog entry ("Josh", 5-star, DPS).
    PlayerCharacter     -- one player's owned copy of a template. Level, XP,
                            dupe count, and equipment all live here so two
                            players (or two pulls of the same template) never
                            share state.
    SquadSlot            -- which 4 PlayerCharacters (in which order) a
                            player currently brings on runs. Slot 0 is
                            always the player's own avatar character.

Only the player's avatar template (is_player_avatar=True) can freely switch
CharacterClass -- that changes its character skill + ultimate to match the
new role (see bot/game/combat/factory.py in the Combat Overhaul for how kits
are resolved per class). Pulled characters have a fixed class baked into
their kit.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base
from bot.database.models.enums import CharacterClass

LEVEL_CAP = 100


class CharacterTemplate(Base):
    __tablename__ = "character_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    star_rating: Mapped[int] = mapped_column(Integer, default=3)  # 3-5
    character_class: Mapped[CharacterClass] = mapped_column(default=CharacterClass.DPS)
    bio: Mapped[str] = mapped_column(String(512), default="")

    # Only true for the single "You" template -- the player's own avatar,
    # which can switch class freely instead of having one baked in.
    is_player_avatar: Mapped[bool] = mapped_column(Boolean, default=False)

    # Base stats at level 1. Growth toward level 100 is linear per
    # `growth_per_level` (a marginal, deliberately slow curve per the
    # balancing pass -- see docs/CHARACTER_LEVELING.md).
    base_hp: Mapped[int] = mapped_column(Integer, default=1000)
    base_attack: Mapped[int] = mapped_column(Integer, default=50)
    base_defense: Mapped[int] = mapped_column(Integer, default=40)
    base_mana: Mapped[int] = mapped_column(Integer, default=100)
    base_elemental: Mapped[int] = mapped_column(Integer, default=30)
    base_speed: Mapped[int] = mapped_column(Integer, default=100)
    base_crit_rate: Mapped[int] = mapped_column(Integer, default=5)      # percent
    base_crit_damage: Mapped[int] = mapped_column(Integer, default=150)  # percent
    base_recharge: Mapped[int] = mapped_column(Integer, default=10)       # percent of mana/energy per basic attack
    base_energy: Mapped[int] = mapped_column(Integer, default=50)       # ultimate always triggers at 50 energy

    # Flat amount added to the matching base_* stat per level (1 -> 100).
    growth_hp: Mapped[float] = mapped_column(Float, default=25.0)
    growth_attack: Mapped[float] = mapped_column(Float, default=1.4)
    growth_defense: Mapped[float] = mapped_column(Float, default=1.1)
    growth_mana: Mapped[float] = mapped_column(Float, default=1.5)
    growth_elemental: Mapped[float] = mapped_column(Float, default=0.9)
    growth_speed: Mapped[float] = mapped_column(Float, default=0.35)

    # String keys resolved against the skill/ultimate/passive registries
    # built in the Combat Overhaul (bot/game/combat/skills.py). Kept as
    # plain strings here so content (this table) doesn't import combat code.
    skill_id: Mapped[str] = mapped_column(String(64), default="")
    ultimate_id: Mapped[str] = mapped_column(String(64), default="")
    passive_id: Mapped[str] = mapped_column(String(64), default="")

    # For the avatar template, one skill_id/ultimate_id per class it can
    # switch into -- kept out of this table (see CLASS_KIT_MAP in
    # bot/game/combat/factory.py) since it's a fixed mapping, not per-row data.

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CharacterTemplate {self.name!r} {self.star_rating}★ {self.character_class}>"


class PlayerCharacter(Base):
    __tablename__ = "player_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("character_templates.id"))

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    # Player-chosen display name, currently only ever set on the player's
    # own avatar character (template.is_player_avatar) -- see
    # character_service.rename_avatar / the /rename command. NULL means
    # "no custom name set yet", i.e. still shows the template's own name
    # ("You" for the avatar) -- see the display_name property below.
    custom_name: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Persisted between battles -- NULL means "full HP" (nothing to clamp
    # yet, e.g. a freshly pulled or leveled character). Combat reads this
    # in via factory.build_character_combatant and writes it back out via
    # combat_service after every battle, so HP no longer silently resets
    # to a flat 100 between fights.
    current_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # How many total copies (including the first) the player has pulled.
    # Every pull beyond the first is a "dupe" and converts to resources
    # instead of granting a second copy -- see character_gacha_service.py.
    dupe_count: Mapped[int] = mapped_column(Integer, default=1)

    # Only meaningful when template.is_player_avatar is True. NULL means
    # "use the template's own class" (always the case for pulled characters).
    current_class: Mapped[CharacterClass | None] = mapped_column(nullable=True)

    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="characters")  # noqa: F821
    template: Mapped["CharacterTemplate"] = relationship()
    equipped_items: Mapped[list["InventoryItem"]] = relationship(  # noqa: F821
        back_populates="character"
    )

    def xp_to_next_level(self) -> int:
        return 150 + (self.level - 1) * 60

    def effective_class(self) -> CharacterClass:
        if self.current_class is not None:
            return self.current_class
        return self.template.character_class

    @property
    def display_name(self) -> str:
        """The name to show for this character everywhere -- profile
        embeds, squad list, and in combat (see
        bot/game/combat/factory.py::build_character_combatant). Falls back
        to the template's own name (e.g. "You" for the avatar) unless the
        player has set a custom_name for this specific PlayerCharacter."""
        return self.custom_name or self.template.name

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerCharacter id={self.id} template_id={self.template_id} lvl={self.level}>"


class SquadSlot(Base):
    """One of a player's 4 active squad positions. Slot 0 is always their
    own avatar PlayerCharacter; slots 1-3 are whichever pulled characters
    they've chosen to bring."""
    __tablename__ = "squad_slots"
    __table_args__ = (UniqueConstraint("player_id", "slot_index", name="uq_squad_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    slot_index: Mapped[int] = mapped_column(Integer)  # 0-3
    character_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("player_characters.id", ondelete="SET NULL"), nullable=True
    )

    player: Mapped["Player"] = relationship(back_populates="squad_slots")  # noqa: F821
    character: Mapped["PlayerCharacter | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SquadSlot player_id={self.player_id} slot={self.slot_index} char={self.character_id}>"
