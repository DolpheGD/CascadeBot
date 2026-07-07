import os

import discord
from discord.ext import commands

from bot.config import COMMAND_PREFIX, DEV_MODE, SERVER_ID
from bot.database.db_init import init_db
from bot.database.session import SessionLocal
from bot.services.item_template_service import ensure_item_templates_seeded
from bot.utils.logger import get_logger

logger = get_logger("client")


# basic bot client setup, including command prefix, intents, and cog loading
class CascadeBot(commands.Bot):
    def __init__(self):
        # No privileged intents needed -- everything is slash commands and
        # component interactions (buttons/selects), never raw message
        # content, so intents.default() is sufficient and avoids requiring
        # the privileged Message Content toggle in the Developer Portal.
        intents = discord.Intents.default()

        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)

    async def setup_hook(self):
        logger.info("Initializing database...")
        init_db()

        logger.info("Seeding item template catalog...")
        db = SessionLocal()
        try:
            ensure_item_templates_seeded(db)
        finally:
            db.close()

        # Persistent Views: registered once here, never per-message. Every
        # button/select callback re-derives game state from the DB using
        # interaction.user.id, so these keep working correctly even after
        # this exact restart -- see bot/cogs/dungeon.py for why.
        from bot.cogs.dungeon import CombatView, DungeonView
        self.add_view(DungeonView())
        self.add_view(CombatView())

        if DEV_MODE:
            # clear the guild command tree to avoid duplicates when reloading
            guild = discord.Object(id=SERVER_ID)
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)

        for filename in os.listdir("bot/cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                await self.load_extension(f"bot.cogs.{filename[:-3]}")
                logger.info("Loaded cog: %s", filename)

    async def on_ready(self):
        try:
            if DEV_MODE:
                guild = discord.Object(id=SERVER_ID)
                synced = await self.tree.sync(guild=guild)
                logger.info("Synced %d guild command(s).", len(synced))
            else:
                synced = await self.tree.sync()
                logger.info("Synced %d global command(s).", len(synced))
        except Exception:
            logger.exception("Failed to sync commands.")

        logger.info("Logged in as %s", self.user)


def run_bot():
    from bot.config import DISCORD_TOKEN

    bot = CascadeBot()
    bot.run(DISCORD_TOKEN)
