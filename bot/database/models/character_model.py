"""
Characters -- the core of the Combat Overhaul.

The gacha now pulls CHARACTERS, not gear (see
bot/game/economy/character_gacha_config.py and
bot/services/character_gacha_service.py). Every character -- including your own
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
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base
from bot.database.models.enums import CharacterClass

# Imported for type checkers only -- SQLAlchemy resolves these names from its
# own class registry at mapper-configuration time, so importing them at runtime
# would only create import cycles between the model modules.
if TYPE_CHECKING:  # pragma: no cover
    from bot.database.models.equipment_model import InventoryItem
    from bot.database.models.player_model import Player

LEVEL_CAP = 100

# Imported so effective_star can clamp without importing the whole
# economy package into the model layer (which would cycle: config ->
# models -> config).
MAX_STAR = 5


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

    # TALENTS: the list of bought node ids, e.g. ["a1", "a2", "b1"].
    #
    # A list of ids and nothing else -- no points-spent total, no cached
    # stat bonus. Both of those are derivable from this list plus the
    # config, and storing a derived value alongside its source is how the
    # two end up disagreeing after a config retune. Points spent is
    # recomputed on read (talent_service.spent_points); the stat bonus is
    # recomputed per combat build.
    talents: Mapped[list] = mapped_column(JSON, default=list)

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

    # EVOLUTION: how many times this copy has been evolved up the star
    # ladder. See bot/game/economy/character_evolution_config.py.
    #
    # It lives HERE and not on the template, and that is not a style
    # choice -- CharacterTemplate.star_rating is shared by every player
    # who owns that character. Evolving by writing to the template would
    # promote Andy to 5 stars for the entire server the moment one person
    # paid for it, and would corrupt the gacha tables, the Echo prices
    # and the card system on the way past, since all of them read that
    # same field.
    #
    # Stored as a COUNT rather than the resulting star rating, so the
    # native rating stays readable from the template and the two can
    # never disagree about where a character started. effective_star
    # below is the only place they are combined.
    evolution_stage: Mapped[int] = mapped_column(Integer, default=0)

    # Only meaningful when template.is_player_avatar is True. NULL means
    # "use the template's own class" (always the case for pulled characters).
    current_class: Mapped[CharacterClass | None] = mapped_column(nullable=True)

    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="characters")
    template: Mapped["CharacterTemplate"] = relationship()
    equipped_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="character"
    )

    # ------------------------------------------------------------------
    # THE XP CURVE IS GEOMETRIC, not linear.
    #
    # It used to be `150 + (level - 1) * 60`, and the problem with a
    # linear cost is not the cost -- it is the SHAPE OF THE STEP:
    #
    #     lv 1 -> 2    150      +40% over the previous level
    #     lv 3 -> 4    270      +29%
    #     lv 20 -> 21  1,290    +5%
    #     lv 40 -> 41  2,490    +2%
    #     lv 99 -> 100 6,030    +1%
    #
    # So the first level-up arrives almost instantly and feels enormous,
    # the next few come fast, and from about level 30 onwards every level
    # costs practically what the last one did. That is the reported "huge
    # jump at 1-2 and then it plateaus" exactly: a linear formula has a
    # decaying relative step by construction.
    #
    # A geometric curve makes the step CONSTANT -- every level costs
    # ~5.5% more than the one before it, forever -- which is what
    # "gradual" actually means, and it lets the two ends be far apart
    # without any point in the middle feeling like a wall:
    #
    #     lv 1 -> 2       90
    #     lv 50 -> 51  1,241
    #     lv 99 -> 100 17,100
    #
    # Total to level 100 is 326k against the old 312k, so the overall
    # grind is deliberately unchanged -- this redistributes the cost
    # along the curve rather than making levelling longer. A power curve
    # was tried first and is worse at the thing being fixed: it starts
    # with a 2.47x step, which is more front-loaded than what it replaced.
    # ------------------------------------------------------------------
    XP_BASE = 90
    XP_GROWTH = 1.055

    def xp_to_next_level(self) -> int:
        return round(self.XP_BASE * (self.XP_GROWTH ** (self.level - 1)))

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

    @property
    def effective_star(self) -> int:
        """The star rating to SHOW and to score this copy at.

        Native rating plus evolutions. Every place that displays stars or
        ranks by them should read this rather than template.star_rating,
        so an evolved character is listed and sorted where the player
        expects to find it.

        The exceptions are deliberate and worth naming, because they look
        like bugs otherwise: the gacha tables, the Echo exchange prices
        and the duplicate payouts all keep reading the TEMPLATE. What a
        character costs to buy and what its duplicates are worth are
        facts about the character, not about one player's copy -- pricing
        them off effective_star would make an evolved Andy cost more at
        the shop than an un-evolved one, for everyone.
        """
        return min(MAX_STAR, self.template.star_rating + int(self.evolution_stage or 0))

    @property
    def is_evolved(self) -> bool:
        return int(self.evolution_stage or 0) > 0

    def star_label(self) -> str:
        """Stars as text, with the Evolved tag when it applies.

        One helper so the tag reads identically in every screen. It was
        going to be spelled out at each call site, which is how the same
        character ends up "5★ Evolved" on one screen and "Evolved 5★" on
        the next.
        """
        stars = "★" * self.effective_star
        return f"{stars} Evolved" if self.is_evolved else stars

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

    player: Mapped["Player"] = relationship(back_populates="squad_slots")
    character: Mapped["PlayerCharacter | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SquadSlot player_id={self.player_id} slot={self.slot_index} char={self.character_id}>"


class SquadPreset(Base):
    """A NAMED, SAVED COPY of a squad -- not a second live squad.

    Deliberately stores character ids and nothing else, and loading one
    writes those ids into the player's SquadSlot rows. SquadSlot stays the
    single source of truth for "who is currently fighting", so every
    caller in the game -- combat, story, adventure, raids, the benchmarks
    -- keeps reading the squad exactly as it always did and needs no
    changes at all.

    The alternative (an `active_preset_id` on Player, with combat reading
    through it) would have put a second way to answer "who is in the
    squad" into a codebase whose recurring bug is precisely two code paths
    computing one value.

    A preset can go stale: it stores ids, and a character could in
    principle stop being owned. squad_service.load_preset drops anything
    the player no longer has rather than failing, so an old preset
    degrades to a partial squad instead of an error.
    """
    __tablename__ = "squad_presets"
    __table_args__ = (UniqueConstraint("player_id", "name", name="uq_squad_preset_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(32))
    # [character_id | None] * 4, index = slot. JSON rather than four
    # columns so the slot count can change without a migration.
    character_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SquadPreset player_id={self.player_id} name={self.name!r}>"
