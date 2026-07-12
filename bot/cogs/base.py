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
from bot.services.player_service import get_player
from bot.services import base_service, dungeon_service, mailbox_service
from bot.game.economy.hq_config import is_max_hq_level, upgrade_requirements
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
        "all grow with HQ level -- use `/harvesters`, `/shrines`, `/mailbox`, and `/shop`."
    )

    if is_max_hq_level(base.hq_level):
        embed.add_field(name="Status", value="Cascade HQ is at its maximum level.", inline=False)
        return embed

    cost = upgrade_requirements(base.hq_level)["upgrade_cost"]
    cost_text = ", ".join(f"{amount} {currency}" for currency, amount in cost.items())
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
        cost_text = "/".join(f"{amount}{currency[:1]}" for currency, amount in cost.items())
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
            value = f"Not built - Build cost: {template.build_cost_gold} gold"
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
                template.id, label=f"Build {template.name} ({template.build_cost_gold}g)",
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
                label=f"Upgrade {template.name} (Lv{owned_shrine.level}->{owned_shrine.level + 1}, {cost}g)",
                style=discord.ButtonStyle.primary,
            ))
    return ShrineView(buttons, owner_id=player.id)


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


def _build_shop_embed(db, player) -> discord.Embed:
    hq_level = base_service.get_hq_level(db, player)
    listings = base_service.list_shop_listings(db, hq_level)

    embed = discord.Embed(title="Local Shop", color=discord.Color.orange())
    embed.description = "Low-level goods and material exchanges. More unlocks as Cascade HQ levels up."
    for listing in listings:
        value = f"{listing.description}\nCost: {listing.cost_amount} {listing.cost_currency}"
        if listing.daily_limit:
            value += f" (max {listing.daily_limit}/day)"
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
            listing.id, label=f"Buy {listing.name} ({listing.cost_amount} {listing.cost_currency})",
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
        cost_text = ", ".join(f"{amount} {currency}" for currency, amount in cost.items())
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
        cost_text = "/".join(f"{amount}{currency[:1]}" for currency, amount in cost.items())
        upgrade_button = MailboxUpgradeButton(label=f"Upgrade Mailbox ({cost_text})", style=discord.ButtonStyle.primary)

    return MailboxView(collect_button, upgrade_button, owner_id=player.id)


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

@guild_decorator
class Base(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
            base_service.ensure_base_catalog_seeded(db)
        finally:
            db.close()

    @app_commands.command(name="base", description="View and upgrade your Cascade HQ.")
    async def base_cmd(self, ctx: discord.Interaction):
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
