import os

import discord
from discord.ext import commands

from bot.config import COMMAND_PREFIX, DEV_MODE, SERVER_ID
from bot.database.db_init import init_db
from bot.database.session import SessionLocal
from bot.services.character_template_service import ensure_character_templates_seeded
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

        # LAST LINE OF DEFENCE FOR AN EXPIRED INTERACTION.
        #
        # Every command now defers before touching the database (see
        # bot/utils/responses.py), which is what actually prevents this.
        # But deferring can only help once the handler has been ENTERED
        # -- if the process is blocked for three seconds before dispatch
        # (a gateway resume, or SQLite holding its database-wide write
        # lock while an expedition commits), the token is already dead
        # and there is no reply to be made through any code path.
        #
        # There is no user-visible difference between logging that and
        # raising it: the reply was never going to arrive either way. The
        # difference is in the log, where a five-frame traceback for "the
        # network was slow" buries the bugs that are worth reading. So
        # 10062 becomes one line, and everything else still raises.
        self.tree.on_error = self._on_app_command_error
        self.tree.interaction_check = self._time_command

    async def _on_app_command_error(self, interaction: discord.Interaction, error):
        from discord import app_commands

        from bot.utils.responses import UNKNOWN_INTERACTION

        original = getattr(error, "original", error)
        if isinstance(original, discord.NotFound) \
                and getattr(original, "code", None) == UNKNOWN_INTERACTION:
            name = interaction.command.qualified_name if interaction.command else "?"
            logger.warning(
                "/%s: interaction expired before it could be answered "
                "(the bot was busy for >3s; nothing was sent)", name,
            )
            return
        if isinstance(error, app_commands.CheckFailure):
            return  # already reported to the user by the check itself

        # Anything else: tell the player, then log it. This used to
        # re-raise, which logged a traceback and left the player staring
        # at a command that silently did nothing -- see
        # responses.report_failure for why a dead end with no message is
        # the worst available outcome.
        from bot.utils import responses

        name = interaction.command.qualified_name if interaction.command else "?"
        await responses.report_failure(interaction, original, where=f"/{name}")


    # ------------------------------------------------------------------
    # Command timing, and naming the work for the watchdog
    # ------------------------------------------------------------------
    #
    # `interaction_check` runs before every application command, and
    # `on_app_command_completion` after it, so between them they measure
    # the real wall-clock cost of a command as the player experiences it.
    #
    # WHY THIS IS WORTH ITS OWN HOOK. The gateway warning ("Can't keep
    # up, websocket is 20.4s behind") says the loop was blocked and
    # nothing about by what. Per-command timings turn that into a
    # ranked list of what to fix -- and the ContextVar set here is what
    # lets the watchdog name the culprit rather than reporting an
    # anonymous stall.
    async def _time_command(self, interaction: discord.Interaction) -> bool:
        import time as _time

        name = interaction.command.qualified_name if interaction.command else "?"
        label = f"/{name} (user {interaction.user.id})"
        interaction.extras["_started"] = _time.perf_counter()
        # note() rather than a ContextVar set: the watchdog runs in its
        # own task and cannot see another task's context. See the note in
        # watchdog.py -- the ContextVar version reported every block as
        # "no command" while looking entirely correct.
        from bot.utils import watchdog
        watchdog.note(label)
        return True

    async def on_app_command_completion(self, interaction, command):
        import time as _time

        started = interaction.extras.get("_started")
        if started is None:
            return
        elapsed = _time.perf_counter() - started
        name = getattr(command, "qualified_name", "?")
        # 3s is Discord's interaction deadline. A command that takes
        # longer than that only worked because it deferred in time, and
        # is one slow query away from not working at all.
        if elapsed >= 3.0:
            logger.warning("/%s took %.1fs -- past Discord's 3s deadline; it "
                           "survived only because it deferred", name, elapsed)
        elif elapsed >= 1.0:
            logger.info("/%s took %.1fs", name, elapsed)

    async def setup_hook(self):
        # WATCHDOG FIRST, before any of the slow setup below.
        #
        # setup_hook itself runs init_db() and seeds three catalogs
        # synchronously, which is one of the longest blocks the process
        # ever performs. Starting the watchdog here means that block is
        # the first thing it reports, which is exactly right: if boot
        # blocks for ten seconds the log should say so rather than
        # leaving somebody wondering why the bot was late.
        from bot.utils import watchdog
        self._watchdog = watchdog.start(self)

        logger.info("Initializing database...")
        init_db()

        logger.info("Seeding item template catalog...")
        db = SessionLocal()
        try:
            ensure_item_templates_seeded(db)
            ensure_character_templates_seeded(db)
        finally:
            db.close()

        # Persistent Views/DynamicItems: registered once here, never
        # per-message. Every button/select callback re-derives game state
        # from the DB using interaction.user.id, so these keep working
        # correctly even after this exact restart -- see bot/cogs/dungeon.py
        # for why. DynamicItems (harvester actions, inventory nav/equip/
        # upgrade) additionally carry per-click target data (item id,
        # template id, entry id) baked into their custom_id, matched via
        # regex on reconnect. Plain fixed-custom_id Selects/Buttons need a
        # registered dummy instance so their custom_id is in the fallback
        # routing table too -- the dummy's *options* don't matter (Discord
        # delivers the real ones the user saw), only its custom_id does, so
        # every conditionally-shown component gets a non-empty placeholder
        # here to guarantee its custom_id is actually registered.
        from bot.cogs.dungeon import CombatView, DungeonView, StartBattleView
        from bot.cogs.inventory import (
            EntryAddSubstatButton,
            EntryEquipToggleButton,
            EntryLevelUpButton,
            EntryNavButton,
            EntryOpenLootboxButton,
            EntryRerollButton,
            EntrySellButton,
            InventoryListView,
            InventorySelectEntry,
            ListPageButton,
            ToListButton,
        )
        from bot.cogs.base import (
            HarvesterActionButton,
            HarvesterCollectAllButton,
            HQUpgradeButton,
            ForgeCraftButton,
            ForgeUpgradeButton,
            LabUpgradeButton,
            ResearchCollectButton,
            ResearchStartButton,
            ShopBuyButton,
            ShopCategoryButton,
            ShrineActionButton,
        )
        from bot.cogs.quests import RollQuestButton
        from bot.cogs.raid import RaidActionView, RaidSummonButton

        dummy_ability_options = [discord.SelectOption(label="dummy", value="dummy")]
        dummy_target_options = [discord.SelectOption(label="dummy", value="0")]

        self.add_view(DungeonView())
        self.add_view(StartBattleView())
        self.add_view(CombatView(
            ability_options=dummy_ability_options,
            target_options=dummy_target_options,
            ultimate_ready=True,
            ultimate_exists=True,
        ))
        self.add_view(InventoryListView(InventorySelectEntry(), []))
        self.add_dynamic_items(
            EntryNavButton, ToListButton, EntryEquipToggleButton,
            EntryLevelUpButton, EntryRerollButton, EntryAddSubstatButton, EntrySellButton,
            EntryOpenLootboxButton, ListPageButton,
        )
        self.add_dynamic_items(HarvesterActionButton, HarvesterCollectAllButton)
        self.add_dynamic_items(HQUpgradeButton, ShrineActionButton, ShopBuyButton, ShopCategoryButton)
        self.add_dynamic_items(
            ResearchStartButton, ResearchCollectButton, LabUpgradeButton,
            ForgeUpgradeButton, ForgeCraftButton,
        )
        self.add_dynamic_items(RollQuestButton)
        # Both gacha banners share one persistent view (bot/utils/banner_ui.py),
        # so one registration covers /pull and /cardpull -- and any banner
        # added later, since the button resolves its banner from the
        # custom_id rather than from which cog built it.
        from bot.utils.banner_ui import BannerButton
        from bot.cogs.cards import CardActionButton, CardPullButton
        from bot.cogs.cards import CardBackButton, CardNavButton, CardPageButton
        self.add_dynamic_items(BannerButton, CardActionButton, CardPullButton,
                               CardPageButton, CardBackButton, CardNavButton)
        # Raids: the action view is timeout=None and must survive restarts
        # (a raid runs for a week -- see raid_config.RAID_DURATION, which
        # is far longer than any bot uptime should be assumed to be).
        self.add_view(RaidActionView())
        self.add_dynamic_items(RaidSummonButton)

        if DEV_MODE:
            # clear the guild command tree to avoid duplicates when reloading
            guild = discord.Object(id=SERVER_ID)
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)

        for filename in os.listdir("bot/cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                await self.load_extension(f"bot.cogs.{filename[:-3]}")
                logger.info("Loaded cog: %s", filename)

    async def on_interaction(self, interaction: discord.Interaction):
        """Record that this player is active in this guild.

        Leaderboards are per-server, and Discord will not tell us who is
        in a server without the privileged `members` intent (which this
        bot deliberately doesn't request -- see __init__). So we track it
        ourselves, from the one place every command, button and select
        passes through.

        Wrapped in a blanket except on purpose: this is bookkeeping
        attached to every interaction in the game, and a failure to write
        a leaderboard row must never break the action the player actually
        pressed."""
        try:
            if interaction.guild_id is None or interaction.user.bot:
                return
            from bot.services import presence_service

            db = SessionLocal()
            try:
                presence_service.record_seen(db, interaction.user.id, interaction.guild_id)
                # last_seen_at rides the SAME listener, deliberately.
                #
                # It drives the "while you were away" summary, and the
                # one thing that summary must not do is misreport how
                # long somebody was gone. Stamping it per-cog would mean
                # every new command is a chance to forget, and the
                # symptom -- a welcome-back screen that says "3 days"
                # to someone who played yesterday -- looks like a bug in
                # the summary rather than a missing line in a cog.
                #
                # ORDERING TRAP, and it is why touch_last_seen does not
                # simply write the current time. on_interaction fires
                # BEFORE the command handler runs, so stamping "now" here
                # would overwrite the very gap the summary needs to
                # measure -- every player would read as zero hours away
                # and the welcome-back screen would never appear once.
                #
                # So touch_last_seen leaves a long gap ALONE. The stamp
                # is advanced by away_service.mark_shown() after the
                # summary has actually been displayed, which also means a
                # player cannot miss it by happening to run a command
                # that does not render it.
                presence_service.touch_last_seen(db, interaction.user.id)
            finally:
                db.close()
        except Exception:  # pragma: no cover - never break an interaction
            logger.debug("Could not record guild presence", exc_info=True)

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
