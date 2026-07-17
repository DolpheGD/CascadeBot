"""
/quests -- beginner quests (one-time, complete-all-for-a-bonus) and the
repeating basic quest (reroll every 5 hours). All the actual assignment/
progress-tracking logic lives in bot/services/quest_service.py; this cog
is just the view layer.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import quest_service
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner


def _quest_embed_and_view(db, player) -> tuple[discord.Embed, "QuestView"]:
    beginner_quests = quest_service.get_beginner_quests(db, player)
    basic_quest = quest_service.get_active_basic_quest(db, player)
    cooldown_remaining = quest_service.basic_quest_cooldown_remaining(player)

    embed = embedder.quest_board_embed(beginner_quests, basic_quest, cooldown_remaining, player)
    can_roll = cooldown_remaining is None
    view = QuestView(show_roll_button=can_roll, owner_id=player.id)
    return embed, view


class RollQuestButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_quest_roll"):
    def __init__(self):
        super().__init__(discord.ui.Button(
            label="🎲 Get New Quest", style=discord.ButtonStyle.success, custom_id="cascade_quest_roll",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        await _handle_roll_quest(interaction)


class QuestView(OwnedView):
    def __init__(self, show_roll_button: bool = False, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        if show_roll_button:
            self.add_item(RollQuestButton())


async def _handle_roll_quest(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        try:
            quest_service.roll_basic_quest(db, player)
        except quest_service.QuestOnCooldown as exc:
            hours, remainder = divmod(int(exc.time_remaining.total_seconds()), 3600)
            minutes = remainder // 60
            await interaction.response.send_message(
                f"Your next basic quest isn't ready yet -- come back in {hours}h {minutes}m.",
                ephemeral=True,
            )
            return

        embed, view = _quest_embed_and_view(db, player)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


@guild_decorator
class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quests", description="View your beginner and basic quests.")
    async def quests(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return
            embed, view = _quest_embed_and_view(db, player)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Quests(bot))
