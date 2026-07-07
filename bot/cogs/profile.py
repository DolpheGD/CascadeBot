import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_or_create_player, get_player
from bot.services.currency_service import add_currency
from bot.utils.guild_decorator import guild_decorator
from bot.utils.embedder import profile_embed

STARTING_GOLD = 150


@guild_decorator
class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /start
    # Creates a new player profile for the user, if one doesn't already exist.
    @app_commands.command(
        name="start",
        description="Begin your CascadeBot journey."
    )
    async def start(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            existing = get_player(db, ctx.user.id)
            if existing is not None:
                await ctx.response.send_message(
                    f"You've already begun your journey, {existing.username}. "
                    "Use `/profile` to check your progress.",
                    ephemeral=True,
                )
                return

            get_or_create_player(db, ctx.user.id, ctx.user.display_name)
            player = get_player(db, ctx.user.id)
            add_currency(db, player, "gold", STARTING_GOLD)
        finally:
            db.close()

        await ctx.response.send_message(
            f"Welcome to the Cascade, **{ctx.user.display_name}**. "
            f"Your journey begins at level 1 with {STARTING_GOLD} gold to get started. "
            "Use `/profile` any time to check your stats."
        )

    # COMMAND: /profile
    # Displays the caller's CascadeBot profile: class, level, xp, gold, and stats.
    @app_commands.command(
        name="profile",
        description="View your CascadeBot profile."
    )
    async def profile(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            embed = await profile_embed(player)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
