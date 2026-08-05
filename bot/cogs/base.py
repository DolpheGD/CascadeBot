"""
Cascade HQ, shrines, and the shop -- the base-building layer that sits on
top of harvesters (bot/cogs/economy.py). Same UI shape as harvesters:
DynamicItem buttons that re-derive everything from the DB on every click,
grouped under OwnedView so only the invoking player can use their own menu.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.database.models.hq_model import ShopListing, ShrineTemplate
from bot.database.models.economy_model import HarvesterTemplate
from bot.services.player_service import get_player
from bot.services import base_service, dungeon_service, forge_service, research_service
from bot.game.economy import forge_config, research_config
from bot.database.models.enums import EquipmentSlot, Rarity
from bot.services.harvester_service import (
    ensure_harvester_templates_seeded,
    list_templates,
    list_player_harvesters,
    buy_harvester,
    collect_harvester,
    upgrade_harvester,
    get_upgrade_cost,
    get_production_rate,
    effective_max_level,
)
from bot.game.economy.hq_config import (
    MATERIAL_GOLD_VALUE,
    is_max_hq_level,
    upgrade_requirements,
)
from bot.services.currency_service import format_currency
from bot.utils.embedder._shared import fit_field
from bot.utils.guild_decorator import guild_decorator
from bot.utils import names
from bot.utils.ui_guard import (OwnedView, check_message_owner, require_feature,
                                require_player)


PERK_LABELS = {
    "loot_rarity_weight": "Loot rarity",
    "relic_offer_size": "Relic choices",
    "upgrade_cost_percent": "Upgrade discount %",
    "domain_energy": "Domain energy",
    "gacha_pity_reduction": "Pity reduction",
    "character_xp_percent": "Character XP %",
    "harvester_percent": "Harvester yield %",
    "shop_discount_percent": "Shop discount %",
    "forge_cost_percent": "Forge discount %",
    "starting_energy": "Starting energy",
}


# ----------------------------------------------------------------------
# Cascade HQ
# ----------------------------------------------------------------------

class HQUpgradeButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_hq_upgrade"):
    def __init__(self, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.success, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style, custom_id="cascade_hq_upgrade", disabled=disabled,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await interaction.response.send_message(
                    "You can't manage Cascade HQ mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            ok, message = base_service.upgrade_hq(db, player)
            embed = _build_hq_embed(db, player)
            view = _build_hq_view(db, player)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class HQView(OwnedView):
    def __init__(self, upgrade_button: HQUpgradeButton, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.add_item(upgrade_button)


def _build_hq_embed(db, player) -> discord.Embed:
    base = base_service.get_or_create_base(db, player)
    embed = discord.Embed(
        title=f"Cascade HQ -- Level {base.hq_level}",
        color=discord.Color.blurple(),
    )
    embed.description = (
        "Your base of operations. Harvesters, shrines, the Research Lab, the Forge "
        "and the shop all grow with HQ level -- use `/harvesters`, `/shrines`, `/lab`, `/forge` and `/shop`."
    )

    if is_max_hq_level(base.hq_level):
        embed.add_field(name="Status", value="Cascade HQ is at its maximum level.", inline=False)
        return embed

    cost = upgrade_requirements(base.hq_level)["upgrade_cost"]
    cost_text = ", ".join(format_currency(currency, amount) for currency, amount in cost.items())
    embed.add_field(name="Next level cost", value=cost_text, inline=False)

    missing = base_service.missing_hq_requirements(db, player)
    if missing:
        preview = "\n".join(f"- {item}" for item in missing[:8])
        if len(missing) > 8:
            preview += f"\n...and {len(missing) - 8} more"
        embed.add_field(name="Still needed", value=preview, inline=False)
    else:
        embed.add_field(name="Still needed", value="Nothing -- ready to upgrade!", inline=False)

    return embed


def _build_hq_view(db, player) -> HQView:
    base = base_service.get_or_create_base(db, player)
    if is_max_hq_level(base.hq_level):
        button = HQUpgradeButton(label="Cascade HQ (MAX)", style=discord.ButtonStyle.secondary, disabled=True)
    else:
        ready, _ = base_service.can_upgrade_hq(db, player)
        cost = upgrade_requirements(base.hq_level)["upgrade_cost"]
        cost_text = "/".join(format_currency(currency, amount) for currency, amount in cost.items())
        button = HQUpgradeButton(
            label=f"Upgrade HQ to Lv{base.hq_level + 1} ({cost_text})",
            style=discord.ButtonStyle.success if ready else discord.ButtonStyle.secondary,
            disabled=not ready,
        )
    return HQView(button, owner_id=player.id)


# ----------------------------------------------------------------------
# Shrines
# ----------------------------------------------------------------------

class ShrineActionButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_shrine_action:(?P<template_id>\d+)"):
    def __init__(self, template_id: int, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.primary, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style,
            custom_id=f"cascade_shrine_action:{template_id}",
            disabled=disabled,
        ))
        self.template_id = template_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["template_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await interaction.response.send_message(
                    "You can't manage shrines mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            hq_level = base_service.get_hq_level(db, player)
            owned = next(
                (s for s in base_service.list_player_shrines(db, player.id) if s.template_id == self.template_id),
                None,
            )
            if owned is None:
                ok, message = base_service.build_shrine(db, player, self.template_id, hq_level)
            else:
                template = db.get(ShrineTemplate, self.template_id)
                if owned.level >= template.max_level:
                    ok, message = False, f"{template.name} is already at max level."
                else:
                    ok, message = base_service.upgrade_shrine(db, player, owned, hq_level)

            embed = _build_shrine_embed(db, player)
            view = _build_shrine_view(db, player)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class ShrineView(OwnedView):
    def __init__(self, action_buttons: list[ShrineActionButton], owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        for button in action_buttons:
            self.add_item(button)


def _build_shrine_embed(db, player) -> discord.Embed:
    hq_level = base_service.get_hq_level(db, player)
    templates = [t for t in base_service.list_shrine_templates(db) if t.unlock_hq_level <= hq_level]
    owned = {s.template_id: s for s in base_service.list_player_shrines(db, player.id)}

    embed = discord.Embed(title="Shrines", color=discord.Color.teal())
    embed.description = "Shrines grant a flat bonus to your whole party's stats, on top of gear."
    for template in templates:
        owned_shrine = owned.get(template.id)
        cap = base_service.shrine_effective_max_level(template, hq_level)
        if owned_shrine:
            bonus = base_service.shrine_bonus_at_level(template, owned_shrine.level)
            suffix = "%" if template.bonus_type == "percent" else ""
            value = (
                f"Owned - Level {owned_shrine.level}/{template.max_level} (cap {cap})\n"
                f"+{bonus:g}{suffix} {template.stat} to the whole party"
            )
        else:
            value = f"Not built - Build cost: {format_currency('gold', template.build_cost_gold)}"
        embed.add_field(name=template.name, value=value, inline=False)

    locked = [t for t in base_service.list_shrine_templates(db) if t.unlock_hq_level > hq_level]
    if locked:
        names = ", ".join(f"{t.name} (HQ {t.unlock_hq_level})" for t in locked)
        embed.add_field(name="Locked", value=names, inline=False)
    return embed


def _build_shrine_view(db, player) -> ShrineView:
    hq_level = base_service.get_hq_level(db, player)
    templates = [t for t in base_service.list_shrine_templates(db) if t.unlock_hq_level <= hq_level]
    owned = {s.template_id: s for s in base_service.list_player_shrines(db, player.id)}

    buttons = []
    for template in templates:
        owned_shrine = owned.get(template.id)
        cap = base_service.shrine_effective_max_level(template, hq_level)
        if owned_shrine is None:
            buttons.append(ShrineActionButton(
                template.id, label=f"Build {template.name} ({format_currency('gold', template.build_cost_gold)})",
                style=discord.ButtonStyle.success,
            ))
        elif owned_shrine.level >= template.max_level:
            buttons.append(ShrineActionButton(
                template.id, label=f"{template.name} (MAX)",
                style=discord.ButtonStyle.secondary, disabled=True,
            ))
        elif owned_shrine.level >= cap:
            buttons.append(ShrineActionButton(
                template.id, label=f"{template.name} (HQ cap {cap})",
                style=discord.ButtonStyle.secondary, disabled=True,
            ))
        else:
            cost = base_service.get_shrine_upgrade_cost(template, owned_shrine.level)
            buttons.append(ShrineActionButton(
                template.id,
                label=f"Upgrade {template.name} (Lv{owned_shrine.level}->{owned_shrine.level + 1}, {format_currency('gold', cost)})",
                style=discord.ButtonStyle.primary,
            ))
    return ShrineView(buttons, owner_id=player.id)


# ----------------------------------------------------------------------
# Unified harvester view: buy, upgrade, and collect all live here instead
# of as separate commands. Each harvester's action button is a DynamicItem
# (persists across restarts, carries the template id in its custom_id) --
# what the button actually *does* (buy vs. upgrade vs. nothing, since it's
# maxed) is decided fresh from the database every click, never baked into
# the button itself.
# ----------------------------------------------------------------------

class HarvesterActionButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_harvester_action:(?P<template_id>\d+)"):
    def __init__(self, template_id: int, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.primary, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style,
            custom_id=f"cascade_harvester_action:{template_id}",
            disabled=disabled,
        ))
        self.template_id = template_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["template_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        await _handle_harvester_action(interaction, self.template_id)


class HarvesterCollectAllButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_harvester_collect_all"):
    def __init__(self):
        super().__init__(discord.ui.Button(
            label="Collect All", style=discord.ButtonStyle.success,
            custom_id="cascade_harvester_collect_all",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        await _handle_harvester_collect_all(interaction)


class HarvesterView(OwnedView):
    def __init__(self, action_buttons: list[HarvesterActionButton], owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        for button in action_buttons:
            self.add_item(button)
        self.add_item(HarvesterCollectAllButton())


def _build_harvester_embed(db, player) -> discord.Embed:
    templates = list_templates(db)
    owned = {h.template_id: h for h in list_player_harvesters(db, player.id)}
    hq_level = base_service.get_hq_level(db, player)

    embed = discord.Embed(title="Harvesters", color=discord.Color.gold())
    locked_lines = []
    for template in templates:
        if hq_level < template.unlock_hq_level:
            locked_lines.append(f"{template.name} -- requires Cascade HQ level {template.unlock_hq_level}")
            continue
        owned_harvester = owned.get(template.id)
        cap = effective_max_level(template, hq_level)
        if owned_harvester:
            rate = get_production_rate(template, owned_harvester.level)
            value = (
                f"Owned - Level {owned_harvester.level}/{template.max_level} (cap {cap})\n"
                f"Producing {format_currency(template.currency, round(rate * 10) / 10)}/hr"
            )
        else:
            cost = "Free" if template.unlock_cost == 0 else format_currency(template.unlock_currency, template.unlock_cost)
            value = f"Not owned - Unlock: {cost}"
        embed.add_field(name=template.name, value=value, inline=False)
    if locked_lines:
        embed.add_field(name="🔒 Locked", value="\n".join(locked_lines), inline=False)
    return embed


def _build_harvester_view(db, player) -> HarvesterView:
    templates = list_templates(db)
    owned = {h.template_id: h for h in list_player_harvesters(db, player.id)}
    hq_level = base_service.get_hq_level(db, player)

    buttons = []
    for template in templates:
        if hq_level < template.unlock_hq_level:
            continue
        owned_harvester = owned.get(template.id)
        cap = effective_max_level(template, hq_level)
        if owned_harvester is None:
            cost_text = "Free" if template.unlock_cost == 0 else format_currency(template.unlock_currency, template.unlock_cost)
            buttons.append(HarvesterActionButton(
                template.id, label=f"Buy {template.name} ({cost_text})",
                style=discord.ButtonStyle.success,
            ))
        elif owned_harvester.level >= template.max_level:
            buttons.append(HarvesterActionButton(
                template.id, label=f"{template.name} (MAX)",
                style=discord.ButtonStyle.secondary, disabled=True,
            ))
        elif owned_harvester.level >= cap:
            buttons.append(HarvesterActionButton(
                template.id, label=f"{template.name} (HQ cap {cap})",
                style=discord.ButtonStyle.secondary, disabled=True,
            ))
        else:
            cost = get_upgrade_cost(template, owned_harvester.level)
            buttons.append(HarvesterActionButton(
                template.id,
                label=f"Upgrade {template.name} (Lv{owned_harvester.level}->{owned_harvester.level + 1}, {format_currency('gold', cost)})",
                style=discord.ButtonStyle.primary,
            ))
    return HarvesterView(buttons, owner_id=player.id)


async def _handle_harvester_action(interaction: discord.Interaction, template_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if dungeon_service.is_in_combat(expedition):
            await interaction.response.send_message(
                "You can't manage harvesters mid-battle -- finish the fight first!",
                ephemeral=True,
            )
            return

        hq_level = base_service.get_hq_level(db, player)
        owned = next(
            (h for h in list_player_harvesters(db, player.id) if h.template_id == template_id),
            None,
        )
        if owned is None:
            ok, message, _ = buy_harvester(db, player, template_id, hq_level=hq_level)
        else:
            template = db.get(HarvesterTemplate, template_id)
            if owned.level >= template.max_level:
                ok, message = False, f"{template.name} is already at max level."
            else:
                ok, message = upgrade_harvester(db, player, owned, hq_level=hq_level)

        embed = _build_harvester_embed(db, player)
        view = _build_harvester_view(db, player)
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


async def _handle_harvester_collect_all(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if dungeon_service.is_in_combat(expedition):
            await interaction.response.send_message(
                "You can't manage harvesters mid-battle -- finish the fight first!",
                ephemeral=True,
            )
            return

        owned = list_player_harvesters(db, player.id)
        totals: dict[str, int] = {}
        for harvester in owned:
            currency = harvester.template.currency
            amount = collect_harvester(db, harvester)
            totals[currency] = totals.get(currency, 0) + amount

        if not owned:
            message = "You don't own any harvesters yet -- buy one below!"
        elif not any(totals.values()):
            message = "Nothing to collect yet - check back later!"
        else:
            parts = [format_currency(currency, amount) for currency, amount in totals.items() if amount]
            message = f"Collected: {', '.join(parts)}"

        embed = _build_harvester_embed(db, player)
        view = _build_harvester_view(db, player)
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


# ----------------------------------------------------------------------
# Shop
# ----------------------------------------------------------------------

class ShopBuyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_shop_buy:(?P<listing_id>\d+)"):
    def __init__(self, listing_id: int, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.primary, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style,
            custom_id=f"cascade_shop_buy:{listing_id}",
            disabled=disabled,
        ))
        self.listing_id = listing_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["listing_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await interaction.response.send_message(
                    "You can't shop mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            hq_level = base_service.get_hq_level(db, player)
            # Read the listing BEFORE purchasing so the tab can be
            # restored afterward -- a buy shouldn't bounce the player back
            # to the default tab, which with a 23-listing market would
            # mean re-navigating after every single transaction. Derived
            # from the listing they just clicked, so it's always the tab
            # they were actually on.
            listing = db.get(ShopListing, self.listing_id)
            category = _shop_category_of(listing) if listing else DEFAULT_SHOP_CATEGORY

            ok, message = base_service.purchase_listing(db, player, self.listing_id, hq_level)

            embed = _build_shop_embed(db, player, category)
            view = _build_shop_view(db, player, category)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


# ----------------------------------------------------------------------
# Shop categories.
#
# The shop grew from 4 listings to 23 when it became a full two-way
# materials market (see bot/game/economy/hq_config.py). That does not fit
# on one screen: Discord caps a message at 25 components AND an embed at
# 25 fields, and even at exactly the limit a 23-button wall is unusable.
#
# So listings are bucketed into tabs, derived from the listing's own data
# rather than a stored column -- no schema change, and a newly authored
# listing files itself automatically. Only one bucket's buy buttons are
# ever on screen at once, which keeps the component count to roughly
# (listings in the biggest bucket + 4 tab buttons), comfortably inside
# the cap.
# ----------------------------------------------------------------------
SHOP_CATEGORIES = [
    ("sell", "💰 Sell"),
    ("buy", "🛒 Buy"),
    ("refine", "⚗️ Refine"),
    ("crates", "🎁 Crates"),
    ("special", "✨ Special"),
]
DEFAULT_SHOP_CATEGORY = "sell"

_MATERIAL_CURRENCIES = set(MATERIAL_GOLD_VALUE)


def _shop_category_of(listing) -> str:
    """Which tab a listing belongs in, inferred from what it trades:
      * material -> gold   = sell
      * gold     -> material = buy
      * material -> material = refine (the tier-conversion recipes)
      * anything else (gold -> shards, and any future non-material trade)
        = special.
    Inferring rather than storing means the bucketing can never disagree
    with the listing's actual arithmetic."""
    # Crates first: they're identified by KIND rather than by what they
    # trade, since a lootbox listing has no reward_currency at all and
    # would otherwise fall through to "special".
    if listing.kind in ("lootbox", "item"):
        return "crates"

    cost_is_material = listing.cost_currency in _MATERIAL_CURRENCIES
    reward_is_material = listing.reward_currency in _MATERIAL_CURRENCIES

    if cost_is_material and reward_is_material:
        return "refine"
    if cost_is_material and listing.reward_currency == "gold":
        return "sell"
    if listing.cost_currency == "gold" and reward_is_material:
        return "buy"
    return "special"


class ShopCategoryButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_shop_cat:(?P<category>\w+)"):
    def __init__(self, category: str, label: str = "...", selected: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary,
            custom_id=f"cascade_shop_cat:{category}",
            row=0,
        ))
        self.category = category

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["category"])

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            embed = _build_shop_embed(db, player, self.category)
            view = _build_shop_view(db, player, self.category)
            await interaction.response.edit_message(content=None, embed=embed, view=view)
        finally:
            db.close()


class ShopView(OwnedView):
    def __init__(self, buy_buttons: list[ShopBuyButton], category: str, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        for key, label in SHOP_CATEGORIES:
            self.add_item(ShopCategoryButton(key, label, selected=(key == category)))
        for button in buy_buttons:
            self.add_item(button)


def _shop_listing_summary(listing) -> str:
    """Exact, unambiguous 'what you give / what you get' line -- always
    derived straight from the listing's numbers, never from hand-written
    copy, so it can't drift out of sync with what actually happens."""
    give = format_currency(listing.cost_currency, listing.cost_amount)
    if listing.kind == "item":
        return f"Give {give} -> Receive 1x {listing.item_template_name} (item level {listing.item_level})"
    if listing.kind == "lootbox":
        return f"Give {give} -> Receive {listing.lootbox_quantity}x {listing.lootbox_tier.title()} Lootbox"
    return f"Give {give} -> Receive {format_currency(listing.reward_currency, listing.reward_amount)}"


def _shop_listing_button_label(listing) -> str:
    if listing.kind == "item":
        return f"Buy {listing.item_template_name} ({format_currency(listing.cost_currency, listing.cost_amount)})"
    if listing.kind == "lootbox":
        return (
            f"Buy {listing.lootbox_quantity}x {listing.lootbox_tier.title()} Lootbox "
            f"({format_currency(listing.cost_currency, listing.cost_amount)})"
        )
    return (
        f"{format_currency(listing.cost_currency, listing.cost_amount)} "
        f"-> {format_currency(listing.reward_currency, listing.reward_amount)}"
    )


SHOP_CATEGORY_BLURB = {
    "sell": "Turn surplus materials into gold. Every material has a price.",
    "buy": "Buy any material outright -- costs more than harvesting it yourself.",
    "refine": "Convert materials into the tier above. Limited per day.",
    "crates": "Sealed supply crates. Contents roll from the normal loot tables.",
    "special": "Everything that isn't a material trade.",
}


def _listings_in_category(db, player, category: str):
    hq_level = base_service.get_hq_level(db, player)
    listings = base_service.list_shop_listings(db, hq_level)
    return [l for l in listings if _shop_category_of(l) == category]


def _build_shop_embed(db, player, category: str = DEFAULT_SHOP_CATEGORY) -> discord.Embed:
    listings = _listings_in_category(db, player, category)
    label = next((lbl for key, lbl in SHOP_CATEGORIES if key == category), category.title())

    embed = discord.Embed(title=f"Local Shop -- {label}", color=discord.Color.orange())
    embed.description = SHOP_CATEGORY_BLURB.get(category, "") + "\nMore unlocks as Cascade HQ levels up."

    # One compact line per listing instead of a field each: at up to 8
    # listings per tab, a field apiece was ~24 lines of mostly-repeated
    # boilerplate. The exact give/get arithmetic is still shown in full --
    # that's the part the player is actually comparing.
    lines = []
    for listing in listings:
        line = f"**{listing.name}** — {_shop_listing_summary(listing)}"
        if listing.daily_limit:
            line += f"  *(max {listing.daily_limit}/day)*"
        lines.append(line)

    if lines:
        embed.add_field(name="Available", value=fit_field(lines), inline=False)
    else:
        embed.add_field(
            name="Nothing here yet",
            value="Check back after upgrading Cascade HQ.",
            inline=False,
        )
    embed.set_footer(text="Use the tabs above to switch between selling, buying, refining, and specials.")
    return embed


def _build_shop_view(db, player, category: str = DEFAULT_SHOP_CATEGORY) -> ShopView:
    listings = _listings_in_category(db, player, category)

    # 4 tab buttons occupy row 0, and Discord allows 25 components total,
    # so 20 buy buttons is the hard ceiling. No current category comes
    # close (the biggest is 8), but the slice keeps a future catalog
    # addition from silently producing a message Discord rejects outright.
    buttons = []
    for listing in listings[:20]:
        buttons.append(ShopBuyButton(
            listing.id, label=_shop_listing_button_label(listing),
            style=discord.ButtonStyle.primary,
        ))
    return ShopView(buttons, category, owner_id=player.id)


# ----------------------------------------------------------------------
# Mailbox
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Research Lab + Forge
#
# These replaced the mailbox. Both are one-per-player buildings, so their
# views follow the HQ/mailbox shape (a couple of DynamicItem buttons that
# re-derive state from the DB) rather than the harvester/shrine
# template-list shape.
# ----------------------------------------------------------------------

class ResearchStartButton(discord.ui.DynamicItem[discord.ui.Button],
                          template=r"cascade_research_start:(?P<project_id>[a-z_]+)"):
    def __init__(self, project_id: str, label: str = "...", disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.primary if not disabled else discord.ButtonStyle.secondary,
            custom_id=f"cascade_research_start:{project_id}", disabled=disabled,
        ))
        self.project_id = project_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["project_id"])

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            try:
                result = research_service.start_research(db, player, self.project_id)
                message = f"🔬 Started **{result['project']['name']}**."
            except research_service.ResearchError as exc:
                message = str(exc)
            await interaction.response.edit_message(
                content=message, embed=_build_lab_embed(db, player), view=_build_lab_view(db, player),
            )
        finally:
            db.close()


class ResearchCollectButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_research_collect"):
    def __init__(self, label: str = "...", disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.success if not disabled else discord.ButtonStyle.secondary,
            custom_id="cascade_research_collect", disabled=disabled,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            try:
                unlocked = research_service.collect_research(db, player)
                names = ", ".join(f"**{p['name']}**" for p in unlocked)
                message = f"🔬 Research complete: {names}"
            except research_service.ResearchError as exc:
                message = str(exc)
            await interaction.response.edit_message(
                content=message, embed=_build_lab_embed(db, player), view=_build_lab_view(db, player),
            )
        finally:
            db.close()


class LabUpgradeButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_lab_upgrade"):
    def __init__(self, label: str = "...", disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.success if not disabled else discord.ButtonStyle.secondary,
            custom_id="cascade_lab_upgrade", disabled=disabled,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            _, message = research_service.upgrade_lab(db, player)
            await interaction.response.edit_message(
                content=message, embed=_build_lab_embed(db, player), view=_build_lab_view(db, player),
            )
        finally:
            db.close()


class LabView(OwnedView):
    def __init__(self, buttons: list, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        for b in buttons:
            self.add_item(b)


def _build_lab_embed(db, player) -> discord.Embed:
    lab = research_service.get_or_create_lab(db, player)
    done, total = research_service.research_progress(db, player.id)
    slots = research_config.concurrent_slots(lab.level)
    running = research_service.active_research(db, player.id)

    embed = discord.Embed(
        title=f"🔬 Research Lab -- Level {lab.level}",
        description=(
            f"**{done}/{total}** projects complete · **{len(running)}/{slots}** slots in use\n"
            "Research is permanent and account-wide."
        ),
        color=discord.Color.teal(),
    )

    if running:
        lines = []
        for row in running:
            project = research_config.get_project(row.project_id)
            if research_service.is_finished(row):
                lines.append(f"✅ **{project['name']}** -- ready to collect")
            else:
                ts = int(row.finishes_at.timestamp())
                lines.append(f"⏳ **{project['name']}** -- done <t:{ts}:R>")
        embed.add_field(name="In progress", value="\n".join(lines), inline=False)

    perks = research_service.perk_totals(db, player.id)
    if perks:
        embed.add_field(
            name="Active bonuses",
            value=fit_field([f"{PERK_LABELS.get(k, k)}: **+{v:g}**" for k, v in perks.items()]),
            inline=False,
        )

    # Show only what's actionable plus a taste of what's next -- the full
    # tree is 24 projects and would blow out the embed.
    available, locked = [], []
    for project in research_config.RESEARCH_PROJECTS:
        state, reason = research_service.project_state(db, player, project)
        if state == "available":
            cost = ", ".join(format_currency(c, a) for c, a in project["cost"].items())
            available.append(f"**{project['name']}** ({project['branch']}) — {cost}")
        elif state == "locked" and len(locked) < 4:
            locked.append(f"🔒 {project['name']} — {reason}")
    if available:
        embed.add_field(name="Available now", value=fit_field(available), inline=False)
    if locked:
        embed.add_field(name="Coming up", value=fit_field(locked), inline=False)

    cost = research_config.lab_upgrade_cost(lab.level)
    embed.set_footer(
        text=("Lab at max level." if cost is None else
              "Upgrade the Lab for more slots and faster research.")
    )
    return embed


def _build_lab_view(db, player) -> LabView:
    lab = research_service.get_or_create_lab(db, player)
    buttons: list = []

    ready = research_service.collectable(db, player.id)
    buttons.append(ResearchCollectButton(
        label=f"Collect {len(ready)} finished" if ready else "Nothing to collect",
        disabled=not ready,
    ))

    cost = research_config.lab_upgrade_cost(lab.level)
    if cost is None:
        buttons.append(LabUpgradeButton(label="Research Lab (MAX)", disabled=True))
    else:
        cost_text = "/".join(format_currency(c, a) for c, a in cost.items())
        buttons.append(LabUpgradeButton(label=f"Upgrade Lab to Lv{lab.level + 1} ({cost_text})"))

    # Up to 3 startable projects -- Discord caps components at 25 and the
    # tree is far bigger than that, so the button list is the shortlist
    # and the embed carries the full picture.
    started = 0
    for project in research_config.RESEARCH_PROJECTS:
        if started >= 3:
            break
        state, _ = research_service.project_state(db, player, project)
        if state == "available":
            buttons.append(ResearchStartButton(project["id"], label=f"🔬 {project['name']}"))
            started += 1

    return LabView(buttons, owner_id=player.id)


class ForgeUpgradeButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_forge_upgrade"):
    def __init__(self, label: str = "...", disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.success if not disabled else discord.ButtonStyle.secondary,
            custom_id="cascade_forge_upgrade", disabled=disabled,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            _, message = forge_service.upgrade_forge(db, player)
            await interaction.response.edit_message(
                content=message, embed=_build_forge_embed(db, player), view=_build_forge_view(db, player),
            )
        finally:
            db.close()


class ForgeCraftButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"cascade_forge_craft:(?P<slot>\w+):(?P<rarity>\w+)"):
    def __init__(self, slot: str, rarity: str, label: str = "..."):
        super().__init__(discord.ui.Button(
            label=label[:80], style=discord.ButtonStyle.primary,
            custom_id=f"cascade_forge_craft:{slot}:{rarity}",
        ))
        self.slot = slot
        self.rarity = rarity

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["slot"], match["rarity"])

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            try:
                item_obj = forge_service.craft_item(
                    db, player, EquipmentSlot(self.slot), Rarity(self.rarity),
                )
                message = f"🔨 Forged **{item_obj.display_name}**!"
            except forge_service.ForgeError as exc:
                message = str(exc)
            await interaction.response.edit_message(
                content=message, embed=_build_forge_embed(db, player), view=_build_forge_view(db, player),
            )
        finally:
            db.close()


class ForgeSlotSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Which slot to forge...",
            options=[
                discord.SelectOption(label=s.value.title(), value=s.value, default=(s.value == current))
                for s in EquipmentSlot
            ],
            custom_id="cascade_forge_slot", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            await interaction.response.edit_message(
                embed=_build_forge_embed(db, player, self.values[0]),
                view=_build_forge_view(db, player, self.values[0]),
            )
        finally:
            db.close()


# ----------------------------------------------------------------------
# FORGE OPERATIONS: salvage, reforge, transfer.
#
# All three existed as services from the day the Forge shipped and none
# of them had a single button -- the menu offered Craft and Upgrade and
# nothing else, which is why it read as unfinished. Reforge and Transfer
# were even advertised in the Operations line of the embed as unlocking
# at levels 2 and 4, so the player was told about capabilities they had
# no way to use.
#
# Each is an item-picker, so they share one pattern: a mode select
# switches the view, and the picker lists only items the operation can
# legally act on (unequipped, right type) rather than listing everything
# and failing on click.
# ----------------------------------------------------------------------

FORGE_MODES = [
    ("craft", "🔨 Craft", "Make new gear in a slot and rarity you choose."),
    ("salvage", "♻️ Salvage", "Break gear down into materials of its tier."),
    ("reforge", "🎲 Reforge", "Re-roll an item's ability, keeping its stats."),
    ("transfer", "🔗 Transfer", "Move an ability onto another item of the same type."),
]


def _forge_candidates(db, player, *, same_type_as=None) -> list:
    """Unequipped items this player owns, newest first.

    Equipped gear is excluded at the SOURCE rather than rejected on
    click: every one of these operations refuses equipped items anyway,
    and a dropdown full of choices that error is worse than a short one
    that works."""
    from bot.database.models.equipment_model import InventoryItem

    query = db.query(InventoryItem).filter_by(player_id=player.id, is_equipped=False)
    if same_type_as is not None:
        query = query.filter(InventoryItem.item_type == same_type_as.item_type,
                             InventoryItem.id != same_type_as.id)
    return query.order_by(InventoryItem.id.desc()).limit(25).all()


class ForgeModeSelect(discord.ui.Select):
    def __init__(self, current: str, forge_level: int):
        options = []
        for mode, label, description in FORGE_MODES:
            unlocked = forge_config.operation_unlocked(mode, forge_level)
            need = forge_config.FORGE_UNLOCKS.get(mode, 1)
            options.append(discord.SelectOption(
                label=label if unlocked else f"🔒 {label} (Lv{need})",
                value=mode,
                description=description[:100],
                default=(mode == current),
            ))
        super().__init__(placeholder="Forge operation...", options=options,
                         custom_id="cascade_forge_mode", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            mode = self.values[0]
            forge = forge_service.get_or_create_forge(db, player)
            if not forge_config.operation_unlocked(mode, forge.level):
                need = forge_config.FORGE_UNLOCKS.get(mode, 1)
                await interaction.response.send_message(
                    f"{mode.title()} unlocks at Forge level {need}.", ephemeral=True
                )
                return
            await interaction.response.edit_message(
                embed=_build_forge_embed(db, player, mode=mode),
                view=_build_forge_view(db, player, mode=mode),
            )
        finally:
            db.close()


class ForgeItemSelect(discord.ui.Select):
    """The item picker for salvage/reforge, and the SOURCE picker for
    transfer. `mode` is carried in the custom_id so the callback knows
    which operation the click belongs to."""

    def __init__(self, mode: str, items: list, placeholder: str):
        options = [
            discord.SelectOption(
                label=names.fit_suffix(item.display_name, f"+{item.item_level}", 100),
                value=str(item.id),
                description=f"{item.rarity.value.title()} {item.slot.value}"[:100],
            )
            for item in items
        ] or [discord.SelectOption(label="Nothing available", value="none")]
        super().__init__(placeholder=placeholder, options=options[:25],
                         custom_id=f"cascade_forge_item:{mode}", min_values=1, max_values=1)
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "You have no unequipped gear the Forge can work on.", ephemeral=True
            )
            return
        db = SessionLocal()
        try:
            from bot.database.models.equipment_model import InventoryItem

            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            item = db.get(InventoryItem, int(self.values[0]))
            if item is None or item.player_id != player.id:
                await interaction.response.send_message("You don't own that item.", ephemeral=True)
                return

            message = ""
            try:
                if self.mode == "salvage":
                    name = item.display_name
                    got = forge_service.salvage_item(db, player, item)
                    gained = ", ".join(format_currency(c, a) for c, a in got.items())
                    message = f"♻️ Salvaged **{name}** into {gained or 'nothing usable'}."
                elif self.mode == "reforge":
                    reforged = forge_service.reforge_item(db, player, item)
                    ability = (reforged.active_ability or reforged.passive_ability or {}).get("name")
                    message = (f"🎲 Reforged **{reforged.display_name}** — "
                               f"now carries **{ability}**." if ability else
                               f"🎲 Reforged **{reforged.display_name}**, but it came out blank.")
                elif self.mode == "transfer":
                    # First half of transfer: remember the source and show
                    # the target picker, which only lists same-type items.
                    await interaction.response.edit_message(
                        embed=_build_forge_embed(db, player, mode="transfer", source=item),
                        view=_build_forge_view(db, player, mode="transfer", source=item),
                    )
                    return
            except forge_service.ForgeError as exc:
                message = str(exc)

            await interaction.response.edit_message(
                content=message,
                embed=_build_forge_embed(db, player, mode=self.mode),
                view=_build_forge_view(db, player, mode=self.mode),
            )
        finally:
            db.close()


class ForgeTransferTargetSelect(discord.ui.Select):
    def __init__(self, source, items: list):
        options = [
            discord.SelectOption(
                label=names.fit_suffix(item.display_name, f"+{item.item_level}", 100),
                value=str(item.id),
                description=f"{item.rarity.value.title()} {item.slot.value}"[:100],
            )
            for item in items
        ] or [discord.SelectOption(label="No compatible item", value="none")]
        super().__init__(placeholder=f"Put {source.display_name}'s ability onto..."[:150],
                         options=options[:25],
                         custom_id=f"cascade_forge_target:{source.id}",
                         min_values=1, max_values=1)
        self.source_id = source.id

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "You have no other unequipped item of that type to transfer onto.", ephemeral=True
            )
            return
        db = SessionLocal()
        try:
            from bot.database.models.equipment_model import InventoryItem

            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            source = db.get(InventoryItem, self.source_id)
            target = db.get(InventoryItem, int(self.values[0]))
            if source is None or target is None or {source.player_id, target.player_id} != {player.id}:
                await interaction.response.send_message("You don't own those items.", ephemeral=True)
                return
            try:
                result = forge_service.transfer_ability(db, player, source, target)
                message = f"🔗 Ability moved onto **{result.display_name}**. The donor was consumed."
            except forge_service.ForgeError as exc:
                message = str(exc)
            await interaction.response.edit_message(
                content=message,
                embed=_build_forge_embed(db, player, mode="transfer"),
                view=_build_forge_view(db, player, mode="transfer"),
            )
        finally:
            db.close()


class ForgeView(OwnedView):
    """NOT persistent -- 5 minutes and it expires.

    It used to be timeout=None, which was fine when the Forge was two
    fixed buttons. The operation pickers carry their target in the
    custom_id (`cascade_forge_item:reforge`, `cascade_forge_target:412`),
    and those can't be pre-registered for a restart because the item ids
    don't exist until the menu is built. A view that survives a restart
    with dead selects is worse than one that visibly expires, and the
    Forge is a menu you open, use, and close -- there's nothing here
    worth surviving anything."""

    def __init__(self, buttons: list, selects: list, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        for select in selects:
            self.add_item(select)
        for b in buttons:
            self.add_item(b)


def _build_forge_embed(db, player, slot: str = "weapon", mode: str = "craft",
                       source=None) -> discord.Embed:
    forge = forge_service.get_or_create_forge(db, player)
    ceiling = forge_config.max_craft_rarity(forge.level)

    embed = discord.Embed(
        title=f"🔨 Forge -- Level {forge.level}",
        color=discord.Color.dark_orange(),
    )

    if mode == "craft":
        embed.description = (
            "Craft gear in the slot and rarity you choose instead of waiting on a lucky drop.\n"
            f"Currently forging up to **{ceiling.value.title()}**. "
            "The Forge starts at Rare -- anything below that drops freely already."
        )
        lines = []
        for rarity in forge_config.craftable_rarities(forge.level):
            cost = forge_service.craft_cost(db, player, rarity)
            mats = ", ".join(format_currency(c, a) for c, a in cost["materials"].items())
            lines.append(f"**{rarity.value.title()}** — {format_currency('gold', cost['gold'])}, {mats}")
        embed.add_field(name=f"Craft cost ({slot.title()})", value=fit_field(lines), inline=False)
    elif mode == "salvage":
        embed.description = (
            "Break unequipped gear down into materials of its own rarity tier.\n"
            f"Returns about **{forge_config.SALVAGE_RETURN_PERCENT}%** of what crafting it would cost."
        )
    elif mode == "reforge":
        embed.description = (
            "Re-roll an item's **ability**, keeping its main stat and substats exactly as they are.\n"
            "The counterpart to `/inventory`'s substat reroll -- between them you can fix "
            "either half of an item you almost like."
        )
    elif mode == "transfer":
        if source is not None:
            embed.description = (
                f"Moving the ability from **{source.display_name}**.\n"
                "Pick what it lands on. **The donor is destroyed.**"
            )
        else:
            embed.description = (
                "Move an ability from one item onto another of the same type. "
                "The donor is consumed.\n"
                "Pick the item whose ability you want to KEEP first."
            )

    unlocks = []
    for op, level in forge_config.FORGE_UNLOCKS.items():
        mark = "✅" if forge.level >= level else f"🔒 Lv{level}"
        unlocks.append(f"{mark} {op.title()}")
    embed.add_field(name="Operations", value="  ".join(unlocks), inline=False)

    cost = forge_config.forge_upgrade_cost(forge.level)
    embed.set_footer(
        text=("Forge at max level." if cost is None else
              "Upgrade the Forge to craft rarer gear and unlock reforge/transfer.")
    )
    return embed


def _build_forge_view(db, player, slot: str = "weapon", mode: str = "craft",
                      source=None) -> ForgeView:
    forge = forge_service.get_or_create_forge(db, player)
    buttons: list = []
    selects: list = [ForgeModeSelect(mode, forge.level)]

    if mode == "craft":
        selects.append(ForgeSlotSelect(slot))
        for rarity in forge_config.craftable_rarities(forge.level):
            buttons.append(ForgeCraftButton(slot, rarity.value, label=f"🔨 Forge {rarity.value.title()}"))
    elif mode in ("salvage", "reforge"):
        selects.append(ForgeItemSelect(
            mode, _forge_candidates(db, player),
            placeholder="Salvage which item..." if mode == "salvage" else "Reforge which item...",
        ))
    elif mode == "transfer":
        if source is None:
            selects.append(ForgeItemSelect(
                "transfer", _forge_candidates(db, player),
                placeholder="Take the ability FROM...",
            ))
        else:
            selects.append(ForgeTransferTargetSelect(
                source, _forge_candidates(db, player, same_type_as=source)
            ))

    cost = forge_config.forge_upgrade_cost(forge.level)
    if cost is None:
        buttons.append(ForgeUpgradeButton(label="Forge (MAX)", disabled=True))
    else:
        cost_text = "/".join(format_currency(c, a) for c, a in cost.items())
        buttons.append(ForgeUpgradeButton(label=f"Upgrade Forge to Lv{forge.level + 1} ({cost_text})"))

    # Discord allows 5 action rows; each select takes one. Two selects
    # plus a row of buttons stays comfortably inside that.
    return ForgeView(buttons, selects, owner_id=player.id)


@guild_decorator
class Base(commands.GroupCog, name="base", description="Cascade HQ base-building commands."):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
            base_service.ensure_base_catalog_seeded(db)
            ensure_harvester_templates_seeded(db)
        finally:
            db.close()

    @app_commands.command(name="hq", description="View and upgrade your Cascade HQ.")
    async def hq_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'base'):
                return
            embed = _build_hq_embed(db, player)
            view = _build_hq_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="shrines", description="View, build, and upgrade your shrines.")
    async def shrines_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'base'):
                return
            embed = _build_shrine_embed(db, player)
            view = _build_shrine_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="harvesters", description="View, buy, upgrade, and collect your harvesters.")
    async def harvesters_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'base'):
                return

            embed = _build_harvester_embed(db, player)
            view = _build_harvester_view(db, player)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="shop", description="Browse the local shop.")
    async def shop_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'base'):
                return
            embed = _build_shop_embed(db, player)
            view = _build_shop_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="lab", description="Research permanent, account-wide upgrades.")
    async def lab_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'lab'):
                return
            embed = _build_lab_embed(db, player)
            view = _build_lab_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="forge", description="Craft gear in the slot and rarity you choose.")
    async def forge_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'forge'):
                return
            embed = _build_forge_embed(db, player)
            view = _build_forge_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Base(bot))
