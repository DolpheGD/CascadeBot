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
from bot.database.models.hq_model import ShrineTemplate
from bot.database.models.economy_model import HarvesterTemplate
from bot.services.player_service import get_player
from bot.services import base_service, dungeon_service, mailbox_service
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
from bot.game.economy.hq_config import is_max_hq_level, upgrade_requirements
from bot.services.currency_service import format_currency
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner


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
        "Your base of operations. Harvesters, shrines, the mailbox, and the shop "
        "all grow with HQ level -- use `/harvesters`, `/base shrines`, `/base mailbox`, and `/base shop`."
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
            ok, message = base_service.purchase_listing(db, player, self.listing_id, hq_level)

            embed = _build_shop_embed(db, player)
            view = _build_shop_view(db, player)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class ShopView(OwnedView):
    def __init__(self, buy_buttons: list[ShopBuyButton], owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
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


def _build_shop_embed(db, player) -> discord.Embed:
    hq_level = base_service.get_hq_level(db, player)
    listings = base_service.list_shop_listings(db, hq_level)

    embed = discord.Embed(title="Local Shop", color=discord.Color.orange())
    embed.description = "Low-level goods and material exchanges. More unlocks as Cascade HQ levels up."
    for listing in listings:
        value = f"{listing.description}\n{_shop_listing_summary(listing)}"
        if listing.daily_limit:
            value += f"\n(max {listing.daily_limit}/day)"
        embed.add_field(name=listing.name, value=value, inline=False)
    if not listings:
        embed.add_field(name="Nothing here yet", value="Check back after upgrading Cascade HQ.", inline=False)
    return embed


def _build_shop_view(db, player) -> ShopView:
    hq_level = base_service.get_hq_level(db, player)
    listings = base_service.list_shop_listings(db, hq_level)

    buttons = []
    for listing in listings[:25]:
        buttons.append(ShopBuyButton(
            listing.id, label=_shop_listing_button_label(listing),
            style=discord.ButtonStyle.primary,
        ))
    return ShopView(buttons, owner_id=player.id)


# ----------------------------------------------------------------------
# Mailbox
# ----------------------------------------------------------------------

class MailboxCollectButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_mailbox_collect"):
    def __init__(self, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.success, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style, custom_id="cascade_mailbox_collect", disabled=disabled,
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
                    "You can't check the mailbox mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            _, message, _ = mailbox_service.collect_mailbox(db, player)

            embed = _build_mailbox_embed(db, player)
            view = _build_mailbox_view(db, player)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class MailboxUpgradeButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_mailbox_upgrade"):
    def __init__(self, label: str = "...", style: discord.ButtonStyle = discord.ButtonStyle.primary, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80], style=style, custom_id="cascade_mailbox_upgrade", disabled=disabled,
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
                    "You can't upgrade the mailbox mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            ok, message = mailbox_service.upgrade_mailbox(db, player)

            embed = _build_mailbox_embed(db, player)
            view = _build_mailbox_view(db, player)
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class MailboxView(OwnedView):
    def __init__(self, collect_button: MailboxCollectButton, upgrade_button: MailboxUpgradeButton, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.add_item(collect_button)
        self.add_item(upgrade_button)


def _build_mailbox_embed(db, player) -> discord.Embed:
    mailbox = mailbox_service.get_or_create_mailbox(db, player)
    embed = discord.Embed(title="Mailbox", color=discord.Color.dark_gold())
    embed.description = "A small package of basic supplies arrives every 30min-1hr. Upgrade for better packages."

    if mailbox_service.is_ready(mailbox):
        status = "A package is waiting for you!"
    else:
        remaining = mailbox_service.time_until_ready(mailbox)
        minutes = max(1, int(remaining.total_seconds() // 60))
        status = f"Next package in {minutes}m."
    embed.add_field(name=f"Level {mailbox.level}", value=status, inline=False)

    cost = mailbox_service.get_mailbox_upgrade_cost(mailbox)
    if cost:
        cost_text = ", ".join(format_currency(currency, amount) for currency, amount in cost.items())
        embed.add_field(name="Upgrade cost", value=cost_text, inline=False)
    else:
        embed.add_field(name="Upgrade cost", value="Mailbox is at max level.", inline=False)
    return embed


def _build_mailbox_view(db, player) -> MailboxView:
    mailbox = mailbox_service.get_or_create_mailbox(db, player)
    ready = mailbox_service.is_ready(mailbox)
    collect_button = MailboxCollectButton(
        label="Collect Package" if ready else "Not ready yet",
        style=discord.ButtonStyle.success if ready else discord.ButtonStyle.secondary,
        disabled=not ready,
    )

    cost = mailbox_service.get_mailbox_upgrade_cost(mailbox)
    if cost is None:
        upgrade_button = MailboxUpgradeButton(label="Mailbox (MAX)", style=discord.ButtonStyle.secondary, disabled=True)
    else:
        cost_text = "/".join(format_currency(currency, amount) for currency, amount in cost.items())
        upgrade_button = MailboxUpgradeButton(label=f"Upgrade Mailbox ({cost_text})", style=discord.ButtonStyle.primary)

    return MailboxView(collect_button, upgrade_button, owner_id=player.id)


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

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
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
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
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
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
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
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
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return
            embed = _build_shop_embed(db, player)
            view = _build_shop_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)

    @app_commands.command(name="mailbox", description="Check your mailbox for a package of basic supplies.")
    async def mailbox_cmd(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return
            embed = _build_mailbox_embed(db, player)
            view = _build_mailbox_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Base(bot))
