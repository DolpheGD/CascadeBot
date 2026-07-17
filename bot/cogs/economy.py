import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services.daily_service import claim_daily, DailyOnCooldown
from bot.services import base_service
from bot.services.character_gacha_service import pull_single, pull_multi
from bot.services import character_service, dungeon_service, lootbox_service
from bot.services.currency_service import format_currency
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner
from bot.utils.logger import get_logger

logger = get_logger("economy")




@guild_decorator
class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
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
        materials_text = ", ".join(
            format_currency(material, amount) for material, amount in result["materials"].items()
        )
        if materials_text:
            message += f"\nMaterials: {materials_text}"
        await ctx.response.send_message(message)


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
