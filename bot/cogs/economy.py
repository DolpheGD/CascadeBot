import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.database.models.economy_model import HarvesterTemplate
from bot.services.player_service import get_player
from bot.services.daily_service import claim_daily, DailyOnCooldown
from bot.services.harvester_service import (
    ensure_harvester_templates_seeded,
    list_templates,
    list_player_harvesters,
    buy_harvester,
    collect_harvester,
    upgrade_harvester,
    get_upgrade_cost,
    get_production_rate,
)
from bot.services.gacha_service import pull_single, pull_multi
from bot.services import dungeon_service, lootbox_service
from bot.utils.guild_decorator import guild_decorator


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
        await _handle_harvester_collect_all(interaction)


class HarvesterView(discord.ui.View):
    def __init__(self, action_buttons: list[HarvesterActionButton]):
        super().__init__(timeout=None)
        for button in action_buttons:
            self.add_item(button)
        self.add_item(HarvesterCollectAllButton())


def _build_harvester_embed(db, player) -> discord.Embed:
    templates = list_templates(db)
    owned = {h.template_id: h for h in list_player_harvesters(db, player.id)}

    embed = discord.Embed(title="Harvesters", color=discord.Color.gold())
    for template in templates:
        owned_harvester = owned.get(template.id)
        if owned_harvester:
            rate = get_production_rate(template, owned_harvester.level)
            value = (
                f"Owned - Level {owned_harvester.level}/{template.max_level}\n"
                f"Producing {rate:.1f} {template.currency}/hr"
            )
        else:
            cost = "Free" if template.unlock_cost == 0 else f"{template.unlock_cost} {template.unlock_currency}"
            value = f"Not owned - Unlock: {cost}"
        embed.add_field(name=template.name, value=value, inline=False)
    return embed


def _build_harvester_view(db, player) -> HarvesterView:
    templates = list_templates(db)
    owned = {h.template_id: h for h in list_player_harvesters(db, player.id)}

    buttons = []
    for template in templates:
        owned_harvester = owned.get(template.id)
        if owned_harvester is None:
            cost_text = "Free" if template.unlock_cost == 0 else f"{template.unlock_cost} {template.unlock_currency}"
            buttons.append(HarvesterActionButton(
                template.id, label=f"Buy {template.name} ({cost_text})",
                style=discord.ButtonStyle.success,
            ))
        elif owned_harvester.level >= template.max_level:
            buttons.append(HarvesterActionButton(
                template.id, label=f"{template.name} (MAX)",
                style=discord.ButtonStyle.secondary, disabled=True,
            ))
        else:
            cost = get_upgrade_cost(template, owned_harvester.level)
            buttons.append(HarvesterActionButton(
                template.id,
                label=f"Upgrade {template.name} (Lv{owned_harvester.level}->{owned_harvester.level + 1}, {cost}g)",
                style=discord.ButtonStyle.primary,
            ))
    return HarvesterView(buttons)


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

        owned = next(
            (h for h in list_player_harvesters(db, player.id) if h.template_id == template_id),
            None,
        )
        if owned is None:
            ok, message, _ = buy_harvester(db, player, template_id)
        else:
            template = db.get(HarvesterTemplate, template_id)
            if owned.level >= template.max_level:
                ok, message = False, f"{template.name} is already at max level."
            else:
                ok, message = upgrade_harvester(db, player, owned)

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
            parts = [f"{amount} {currency}" for currency, amount in totals.items() if amount]
            message = f"Collected: {', '.join(parts)}"

        embed = _build_harvester_embed(db, player)
        view = _build_harvester_view(db, player)
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


@guild_decorator
class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
            ensure_harvester_templates_seeded(db)
            lootbox_service.ensure_lootbox_templates_seeded(db)
        finally:
            db.close()

    # COMMAND: /daily
    # Claims the once-per-24h reward. Streak grows the gold bonus and grants
    # bonus shards + lootboxes every 7/30 days.
    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            try:
                result = claim_daily(db, player)
            except DailyOnCooldown as exc:
                hours, remainder = divmod(int(exc.time_remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await ctx.response.send_message(
                    f"You've already claimed today. Come back in {hours}h {minutes}m.",
                    ephemeral=True,
                )
                return
        finally:
            db.close()

        message = f"Daily reward: **{result['gold']} gold** (streak: {result['streak']} days)"
        if result["shards"]:
            message += f" and **{result['shards']} shards** for your streak milestone!"
        tier_counts: dict[str, int] = {}
        for tier in result["lootbox_tiers"]:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        boxes_text = ", ".join(f"{count}x {tier.title()} Lootbox" for tier, count in tier_counts.items())
        if boxes_text:
            message += f"\nAlso received: {boxes_text}"
        await ctx.response.send_message(message)

    # COMMAND: /harvesters
    # View, buy, upgrade, and collect all your harvesters from one place.
    @app_commands.command(name="harvesters", description="View, buy, upgrade, and collect your harvesters.")
    async def harvesters(self, ctx: discord.Interaction):
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

    # COMMAND: /pull
    # Spends shards for a single gacha pull with boosted rarity odds.
    @app_commands.command(name="pull", description="Spend shards on a gacha pull.")
    async def pull(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't pull mid-battle -- finish the fight first!", ephemeral=True
                )
                return

            success, message, _items = pull_single(db, player, item_level=player.level)
        finally:
            db.close()

        await ctx.response.send_message(message, ephemeral=not success)

    # COMMAND: /lootboxes
    # Lists every lootbox tier the player currently owns.
    @app_commands.command(name="lootboxes", description="View your unopened lootboxes.")
    async def lootboxes(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            owned = lootbox_service.list_player_lootboxes(db, player.id)
            if not owned:
                await ctx.response.send_message(
                    "You don't have any lootboxes yet. Try `/daily` or explore a dungeon!",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(title="Your Lootboxes", color=discord.Color.purple())
            for entry in owned:
                embed.add_field(
                    name=entry.template.name,
                    value=f"Quantity: {entry.quantity}\n{entry.template.description}",
                    inline=False,
                )
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)

    # COMMAND: /open
    # Opens every lootbox of the chosen tier at once, rolling gold/shards
    # and item(s) at that tier's boosted rarity odds.
    @app_commands.command(name="open", description="Open all your lootboxes of a given tier.")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Common", value="common"),
        app_commands.Choice(name="Rare", value="rare"),
        app_commands.Choice(name="Epic", value="epic"),
        app_commands.Choice(name="Legendary", value="legendary"),
    ])
    async def open_lootbox(self, ctx: discord.Interaction, tier: str):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't open lootboxes mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            owned = lootbox_service.list_player_lootboxes(db, player.id)
            entry = next((o for o in owned if o.template.tier == tier), None)
            if entry is None:
                await ctx.response.send_message(
                    f"You don't have any {tier.title()} Lootboxes.", ephemeral=True
                )
                return

            ok, message, rewards = lootbox_service.open_lootboxes(
                db, player, tier, count=entry.quantity, item_level=max(player.level, 1)
            )
            if not ok:
                await ctx.response.send_message(message, ephemeral=True)
                return

            embed = discord.Embed(title=message, color=discord.Color.purple())
            embed.add_field(name="Gold", value=str(rewards["gold"]), inline=True)
            if rewards["shards"]:
                embed.add_field(name="Shards", value=str(rewards["shards"]), inline=True)
            if rewards["items"]:
                items_text = "\n".join(
                    f"{item.display_name} ({item.rarity.value})" for item in rewards["items"]
                )
                embed.add_field(name="Items", value=items_text, inline=False)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
