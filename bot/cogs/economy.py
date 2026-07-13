import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.database.models.economy_model import HarvesterTemplate
from bot.services.player_service import get_player
from bot.services.daily_service import claim_daily, DailyOnCooldown
from bot.services import base_service
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
from bot.services.character_gacha_service import pull_single, pull_multi
from bot.services import character_service, dungeon_service, lootbox_service
from bot.services.currency_service import format_currency
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner
from bot.utils.logger import get_logger

logger = get_logger("economy")


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

        message = f"Daily reward: **{format_currency('gold', result['gold'])}** (streak: {result['streak']} days)"
        if result["reroll_tokens"]:
            message += f", **{format_currency('reroll_tokens', result['reroll_tokens'])}**"
        if result["shards"]:
            message += f" and **{format_currency('shards', result['shards'])}** for your streak milestone!"
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
    # Spends shards on a gacha pull -- characters only. Pulling a character
    # you already own converts to gold + reroll tokens instead.
    @app_commands.command(name="pull", description="Spend shards to pull a new character.")
    @app_commands.choices(count=[
        app_commands.Choice(name="Single Pull", value=1),
        app_commands.Choice(name="10x Pull (10% off)", value=10),
    ])
    async def pull(self, ctx: discord.Interaction, count: int = 1):
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

            try:
                if count == 1:
                    success, message, results = pull_single(db, player)
                else:
                    success, message, results = pull_multi(db, player, count=count)

                if not success:
                    await ctx.response.send_message(message, ephemeral=True)
                    return

                embed = embedder.gacha_pull_embed(results)
            except Exception:
                # Surface the real error instead of a silent "This
                # interaction failed" -- makes any future regression here
                # immediately diagnosable instead of a mystery report.
                logger.exception("`/pull` failed for player %s (count=%s)", player.id, count)
                await ctx.response.send_message(
                    "Something went wrong generating your pull results. This has been logged -- "
                    "please report it if it keeps happening.",
                    ephemeral=True,
                )
                return
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)

    # COMMAND: /pull_rates
    # Shows gacha odds by star rating, cost, and the duplicate-conversion rule.
    @app_commands.command(name="pull_rates", description="View gacha odds and pull costs.")
    async def pull_rates(self, ctx: discord.Interaction):
        try:
            embed = embedder.gacha_rates_embed()
        except Exception:
            logger.exception("`/pull_rates` failed to build its embed")
            await ctx.response.send_message(
                "Something went wrong loading gacha rates. This has been logged -- "
                "please report it if it keeps happening.",
                ephemeral=True,
            )
            return
        await ctx.response.send_message(embed=embed, ephemeral=True)

    # COMMAND: /open
    # Opens every lootbox of the chosen tier at once, rolling gold/shards
    # and item(s) at that tier's boosted rarity odds.
    @app_commands.command(name="open", description="Open all your lootboxes of a given tier.")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Common", value="common"),
        app_commands.Choice(name="Uncommon", value="uncommon"),
        app_commands.Choice(name="Rare", value="rare"),
        app_commands.Choice(name="Epic", value="epic"),
        app_commands.Choice(name="Legendary", value="legendary"),
        app_commands.Choice(name="Mythic", value="mythic"),
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
                db, player, tier, count=entry.quantity
            )
            if not ok:
                await ctx.response.send_message(message, ephemeral=True)
                return

            embed = discord.Embed(title=message, color=discord.Color.purple())
            embed.add_field(name="Gold", value=format_currency("gold", rewards["gold"]), inline=True)
            if rewards["shards"]:
                embed.add_field(name="Shards", value=format_currency("shards", rewards["shards"]), inline=True)
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
