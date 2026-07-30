"""
/vote -- top.gg voting rewards.

Flow, and why it takes two runs of the command rather than one:

  1. Player runs /vote. The bot asks top.gg whether they've voted inside
     the current 12h window. They haven't, so it shows what the reward
     would be plus a link button to the vote page.
  2. Player votes on top.gg (external, in a browser).
  3. Player runs /vote again. Top.gg now says yes, and
     vote_service.claim_vote pays out.

Step 3 is a second command rather than automatic because top.gg only
pushes vote notifications to a webhook URL, which needs a publicly
reachable HTTPS endpoint this bot doesn't assume it has -- see
bot/services/topgg_client.py's module docstring. Polling on demand costs
one extra click and needs no hosting at all.

Everything user-visible here is ephemeral: a vote reward is personal, and
the vote link is nicer not spammed into the channel.
"""

from __future__ import annotations

import discord

from discord import app_commands
from discord.ext import commands

from bot.config import TOPGG_BOT_ID
from bot.database.session import SessionLocal
from bot.services import topgg_client, vote_service
from bot.services.player_service import get_player
from bot.services.vote_service import VoteOnCooldown
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.logger import get_logger
from bot.utils.ui_guard import require_player

logger = get_logger("vote")


class VoteLinkView(discord.ui.View):
    """A single link button. Link buttons carry no custom_id and fire no
    interaction, so this needs no persistence or owner guard -- unlike
    every other View in this codebase (see bot/utils/ui_guard.py)."""

    def __init__(self, url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Vote on top.gg", url=url, emoji="🗳️"))


@guild_decorator
class Vote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _bot_id(self) -> int | None:
        """The top.gg listing id. Normally just this bot's own application
        id, resolved from the logged-in user; TOPGG_BOT_ID overrides it for
        the unusual case where they differ. None only if called before the
        bot has finished connecting."""
        if TOPGG_BOT_ID:
            return TOPGG_BOT_ID
        return self.bot.user.id if self.bot.user else None

    # COMMAND: /vote
    # Shows the vote link and the pending reward, or claims a vote that
    # top.gg confirms has happened.
    @app_commands.command(
        name="vote",
        description="Vote for CascadeBot on top.gg for a big Shard bonus (every 12h).",
    )
    async def vote(self, ctx: discord.Interaction):
        if not topgg_client.is_configured():
            await ctx.response.send_message(
                embed=embedder.vote_unconfigured_embed(), ephemeral=True
            )
            return

        bot_id = self._bot_id()
        if bot_id is None:
            await ctx.response.send_message(
                "Still starting up -- try again in a moment.", ephemeral=True
            )
            return

        # The top.gg round-trip can take a second or two, comfortably past
        # Discord's 3s initial-response budget, so defer first.
        await ctx.response.defer(ephemeral=True)

        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            url = topgg_client.vote_url(bot_id)

            # Already paid out for the current window -- don't even ask
            # top.gg, the answer wouldn't change what we do.
            remaining = vote_service.cooldown_remaining(player)
            if remaining is not None:
                await ctx.followup.send(
                    embed=embedder.vote_prompt_embed(
                        vote_service.peek_next_reward(player), url, player,
                        cooldown_remaining=remaining,
                        streak_expires_at=vote_service.streak_expires_at(player),
                    ),
                    view=VoteLinkView(url),
                    ephemeral=True,
                )
                return

            try:
                voted = await topgg_client.has_voted(bot_id, ctx.user.id)
            except topgg_client.TopGGError as exc:
                # TopGGError messages are written to be shown as-is.
                await ctx.followup.send(str(exc), ephemeral=True)
                return

            if not voted:
                await ctx.followup.send(
                    embed=embedder.vote_prompt_embed(
                        vote_service.peek_next_reward(player), url, player,
                        streak_expires_at=vote_service.streak_expires_at(player),
                    ),
                    view=VoteLinkView(url),
                    ephemeral=True,
                )
                return

            is_weekend = await topgg_client.is_weekend()
            try:
                result = vote_service.claim_vote(db, player, is_weekend=is_weekend)
            except VoteOnCooldown as exc:
                # Only reachable if two /vote calls race each other; the
                # pre-check above catches the ordinary case.
                hours, remainder = divmod(int(exc.time_remaining.total_seconds()), 3600)
                await ctx.followup.send(
                    f"You've already claimed this vote. Vote again in {hours}h {remainder // 60}m.",
                    ephemeral=True,
                )
                return
            except Exception:
                logger.exception("/vote payout failed for player %s", player.id)
                await ctx.followup.send(
                    "Something went wrong granting your vote reward. This has been logged -- "
                    "please report it if it keeps happening.",
                    ephemeral=True,
                )
                return

            embed = embedder.vote_claimed_embed(result, player)
        finally:
            db.close()

        await ctx.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Vote(bot))
