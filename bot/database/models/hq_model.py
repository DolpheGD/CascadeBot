"""
Base-building layer that sits on top of the old "just harvesters" economy.

Cascade HQ (PlayerBase) is the hub: it starts at level 1 and gates
everything else -- which harvesters/shrines/shop listings are unlocked
(HarvesterTemplate/ShrineTemplate/ShopListing.unlock_hq_level), and how
high any building can currently be leveled (see
bot/game/economy/hq_config.py::building_level_cap). Upgrading the HQ itself
requires every building unlocked at the current HQ level to be owned and
at that level cap, then spends the HQ's own gold+material cost -- see
bot/services/base_service.py for the actual gating logic.

Shrines (ShrineTemplate/PlayerShrine) mirror the harvester own-a-copy/level-it
shape, but instead of producing currency over time they grant a flat or
percent stat bonus to the whole party, applied on top of character+gear
stats at battle-build time (bot/services/base_service.py::apply_shrine_bonuses).

The shop (ShopListing) is simpler still -- no ownership/leveling, just a
catalog of things purchasable with currency: low-level goods (rolls an
InventoryItem from a specific ItemTemplate) and material exchanges
(currency -> currency conversions). PlayerShopPurchase tracks per-player,
per-listing daily purchase counts for listings with a `daily_limit`.

The mailbox (PlayerMailbox) is simpler still and unique to each player (no
template catalog needed) -- it's created automatically at level 1, always
has exactly one package brewing, and rewards a small basic-supplies package
30min-1hr after the last collection. Its level (and the reward table that
comes with it -- see bot/game/economy/mailbox_config.py) can be upgraded for
better packages; the *wait window* never changes with level.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base_model import Base


class PlayerBase(Base):
    __tablename__ = "player_bases"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    hq_level: Mapped[int] = mapped_column(Integer, default=1)

    player: Mapped["Player"] = relationship(back_populates="base")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerBase player_id={self.player_id} hq_level={self.hq_level}>"


class PlayerMailbox(Base):
    __tablename__ = "player_mailboxes"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    # When the currently-brewing package finishes. Set 30min-1hr out the
    # moment the mailbox is created AND every time a package is collected
    # -- see bot/services/mailbox_service.py.
    next_package_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="mailbox")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerMailbox player_id={self.player_id} level={self.level}>"


class ShrineTemplate(Base):
    __tablename__ = "shrine_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")

    stat: Mapped[str] = mapped_column(String(16))  # one of combat.combatant.STAT_KEYS
    # "flat" adds base_bonus_per_level * level to the stat directly.
    # "percent" adds (base_bonus_per_level * level)% of EACH party member's
    # own base value of that stat -- same "don't compound with itself"
    # rule as gear percent substats (see factory._resolve_gear_stats).
    bonus_type: Mapped[str] = mapped_column(String(8), default="flat")
    base_bonus_per_level: Mapped[float] = mapped_column(Float, default=1.0)

    max_level: Mapped[int] = mapped_column(Integer, default=10)
    unlock_hq_level: Mapped[int] = mapped_column(Integer, default=1)

    build_cost_gold: Mapped[int] = mapped_column(Integer, default=200)
    base_upgrade_cost: Mapped[int] = mapped_column(Integer, default=100)
    upgrade_cost_growth: Mapped[float] = mapped_column(Float, default=1.5)
    upgrade_currency: Mapped[str] = mapped_column(String(16), default="gold")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ShrineTemplate {self.name!r} stat={self.stat}>"


class PlayerShrine(Base):
    __tablename__ = "player_shrines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("shrine_templates.id"))
    level: Mapped[int] = mapped_column(Integer, default=1)

    player: Mapped["Player"] = relationship(back_populates="shrines")  # noqa: F821
    template: Mapped["ShrineTemplate"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerShrine template_id={self.template_id} level={self.level}>"


class ShopListing(Base):
    __tablename__ = "shop_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")

    # "exchange" = spend cost_currency, receive reward_currency.
    # "item" = spend cost_currency, roll one InventoryItem from
    # item_template_name at item_level.
    kind: Mapped[str] = mapped_column(String(16), default="exchange")
    unlock_hq_level: Mapped[int] = mapped_column(Integer, default=1)

    cost_currency: Mapped[str] = mapped_column(String(16), default="gold")
    cost_amount: Mapped[int] = mapped_column(Integer, default=0)

    reward_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reward_amount: Mapped[int] = mapped_column(Integer, default=0)

    item_template_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_level: Mapped[int] = mapped_column(Integer, default=1)

    # 0 = unlimited purchases. Otherwise, max buys per player per 24h --
    # see PlayerShopPurchase / base_service.purchase_listing.
    daily_limit: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ShopListing {self.name!r} kind={self.kind}>"


class PlayerShopPurchase(Base):
    __tablename__ = "player_shop_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE")
    )
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_listings.id"))
    purchased_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerShopPurchase listing_id={self.listing_id} count={self.purchased_count}>"
