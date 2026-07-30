"""
Admin/dev tooling. Currently just one command: /admin_boosterkit, which
grants a specified user a pile of currency and starter lootboxes -- meant
for onboarding/compensation use, not full gear-testing setup, so it works
on anyone regardless of whether they've run /start yet.
"""

from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.config import ADMIN_USER_IDS
from bot.database.session import SessionLocal
from bot.services import lootbox_service
from bot.services.currency_service import add_currency
from bot.services.player_service import get_or_create_player
from bot.utils.guild_decorator import guild_decorator

BOOSTER_GOLD = 10000
BOOSTER_SHARDS = 1000
BOOSTER_LOOTBOXES_PER_TIER = 5
BOOSTER_LOOTBOX_TIERS = ("common", "uncommon", "rare", "epic")


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id in ADMIN_USER_IDS:
        return True
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


@guild_decorator
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /admin_boosterkit
    # Grants the target user a flat pile of currency and starter lootboxes
    # (1000 shards, 10000 gold, 5x each of Common/Uncommon/Rare/Epic
    # lootbox). Uses get_or_create_player rather than requiring the target
    # to have run /start first, so it also works as a way to pre-stock a
    # brand-new player's account. Restricted to server Administrators or
    # IDs listed in the ADMIN_USER_IDS env var.
    @app_commands.command(
        name="admin_boosterkit",
        description="[Admin] Grant a specified user a booster kit of currency and lootboxes.",
    )
    @app_commands.describe(user="The user to grant the booster kit to.")
    async def admin_boosterkit(self, ctx: discord.Interaction, user: discord.Member):
        if not _is_admin(ctx):
            await ctx.response.send_message(
                "You need Administrator permission (or be a configured bot admin) to use this.",
                ephemeral=True,
            )
            return

        await ctx.response.defer(ephemeral=True)

        db = SessionLocal()
        try:
            player = get_or_create_player(db, user.id, user.display_name)

            add_currency(db, player, "gold", BOOSTER_GOLD)
            add_currency(db, player, "shards", BOOSTER_SHARDS)

            for tier in BOOSTER_LOOTBOX_TIERS:
                lootbox_service.grant_lootbox(db, player, tier, BOOSTER_LOOTBOXES_PER_TIER)

            db.commit()
        finally:
            db.close()

        summary = (
            f"🎁 **Booster kit granted to {user.mention}!**\n"
            f"🪙 +{BOOSTER_GOLD:,} gold | 💎 +{BOOSTER_SHARDS:,} shards\n"
            f"📦 +{BOOSTER_LOOTBOXES_PER_TIER} of each: "
            + ", ".join(tier.title() for tier in BOOSTER_LOOTBOX_TIERS) + " lootbox"
        )
        await ctx.followup.send(summary, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
