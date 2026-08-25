"""
The bot's only background scheduler.

WHAT IT IS FOR. Everything in this game is driven by a player pressing a
button, which is a clean design right up to the point where something
needs to happen whether or not anybody is looking: a nightly backup, a
reminder to somebody who has stopped showing up. Before this file there
was no `tasks.loop` anywhere in the codebase and no way to do either.

ONE SCHEDULER, NOT ONE PER FEATURE. Every loop registered here shares the
same three rules, and they exist because a background task that
misbehaves is much harder to notice than a command that does:

  1. IT CAN NEVER CRASH THE BOT. Every task body is wrapped. An
     unhandled exception inside a tasks.loop cancels that loop
     permanently and silently -- the bot keeps running, the backup
     simply stops happening, and nothing says so until the day somebody
     needs a backup.

  2. IT WAITS FOR THE BOT TO BE READY. before_loop/wait_until_ready, or
     the first tick races cog loading and connection setup.

  3. IT LOGS WHAT IT DID, at INFO, every time. A scheduled task that
     succeeds silently is indistinguishable from one that is not running
     at all, and "is the nightly backup actually happening" is a
     question that should be answerable from the log rather than by
     going and looking at the disk.

TIMES ARE UTC AND FIXED, not intervals. `tasks.loop(hours=24)` drifts
with every restart -- restart the bot at 23:50 for a week and the
"nightly" backup wanders across the clock. A fixed `time=` runs at the
same wall-clock moment regardless, which is what "nightly" means and what
makes it predictable for whoever is running the host.
"""

from __future__ import annotations

import datetime as dt

from discord.ext import commands, tasks

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# 04:00 UTC: past midnight in most of the Americas and before the
# European morning, so the backup and the reminder sweep land in the
# quietest part of the day for the largest share of players.
NIGHTLY = dt.time(hour=4, minute=0, tzinfo=dt.timezone.utc)


class Scheduler(commands.Cog):
    """Background maintenance. No slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.nightly_backup.start()
        self.reminder_sweep.start()

    async def _wait_ready(self, which: str) -> None:
        """Rule 2, with rule 1 applied to it as well.

        before_loop is not covered by the try/except inside the task
        body, and an exception raised HERE cancels the loop before it
        ever runs once -- the same permanent, silent death, just earlier.
        wait_until_ready() raises outright if the client was never
        logged in, which is exactly what happens when a test harness or
        a tool loads the cogs to inspect them.
        """
        try:
            await self.bot.wait_until_ready()
        except Exception:
            logger.warning("%s: client never became ready; loop not started", which)
            raise

    async def cog_unload(self):
        self.nightly_backup.cancel()
        self.reminder_sweep.cancel()

    # ------------------------------------------------------------------
    # Nightly backup
    # ------------------------------------------------------------------
    @tasks.loop(time=NIGHTLY)
    async def nightly_backup(self):
        try:
            from bot.config import DATABASE_URL
            from tools.backup_db import run

            destination, pruned = run(DATABASE_URL)
            if destination is None:
                # Not a SQLite deployment. Said once a night at INFO
                # rather than silently skipped, so a Postgres host has a
                # standing reminder that its backups are its own problem.
                logger.info(
                    "Nightly backup skipped: not a SQLite database. "
                    "Back this up with your database's own tooling.")
                return
            logger.info("Nightly backup written to %s (pruned %d old)",
                        destination.name, pruned)
        except Exception:
            # See rule 1. A failed backup must not cancel the loop --
            # tomorrow's attempt should still happen.
            logger.exception("Nightly backup FAILED")

    @nightly_backup.before_loop
    async def _before_backup(self):
        await self._wait_ready("nightly_backup")

    # ------------------------------------------------------------------
    # Reminder sweep
    # ------------------------------------------------------------------
    @tasks.loop(time=NIGHTLY)
    async def reminder_sweep(self):
        try:
            from bot.services import reminder_service

            sent, disabled = await reminder_service.send_due_reminders(self.bot)
            if sent or disabled:
                logger.info("Reminder sweep: %d sent, %d auto-disabled "
                            "(DMs closed)", sent, disabled)
        except Exception:
            logger.exception("Reminder sweep FAILED")

    @reminder_sweep.before_loop
    async def _before_reminders(self):
        await self._wait_ready("reminder_sweep")


async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))
