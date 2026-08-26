"""
Admin/dev tooling.

  /grant -- OWNER ONLY. Gives any user any amount of any resource.

ONE GATE, NOT TWO. /admin_boosterkit used to live here alongside it,
guarded by ADMIN_USER_IDS plus Discord's "Administrator" permission --
and that second, broader gate was removed with it. It was never a real
gate: anyone can create a server, invite the bot, and be an
administrator of it inside a minute, so "Administrator here" is a
permission the whole internet can grant itself. Keeping a config knob
that implies a security boundary it does not enforce is worse than not
having one.

What remains is BOT_OWNER_IDS, which is a list of Discord user IDs and
nothing else, and refuses everybody when it is empty.

Resetting an account used to live here as /admin_reset. It moved to
bot/cogs/account.py as the player-facing /reset, because the admin gate
was never protecting anything: the command was already self-only, so the
permission check only stopped ORDINARY players from starting over --
which is a thing players legitimately want, and which the game is built
to support. See that module for the full reasoning and for prestige.
"""

from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.config import BOT_OWNER_IDS
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services.currency_service import (
    VALID_CURRENCIES, add_currency, format_currency,
)
from bot.utils.logger import get_logger
from bot.services.player_service import get_or_create_player
from bot.utils.guild_decorator import guild_decorator

logger = get_logger(__name__)

# A per-command ceiling. Not a security control -- the owner can simply
# run it again -- but a typo guard: an extra zero on a currency the
# economy is balanced around is a mess to undo, and every column here is
# a plain integer with no upper bound of its own.
MAX_GRANT = 1_000_000_000

# Built from VALID_CURRENCIES rather than typed out, so a currency added
# later is grantable immediately instead of silently missing from the one
# command that exists to hand it out. Discord caps choices at 25; there
# are 14.
_CURRENCY_CHOICES = [
    app_commands.Choice(name=currency.replace("_", " ").title(), value=currency)
    for currency in sorted(VALID_CURRENCIES)[:25]
]


def _is_owner(interaction: discord.Interaction) -> bool:
    """The bot owner, and nobody else. No fallback, ever.

    This is the ONLY permission check left in the bot, and it is a list
    of user IDs. There used to be a second, broader one -- ADMIN_USER_IDS
    plus Discord's "Administrator" permission -- and it was removed along
    with the booster kit it guarded, because it did not guard anything:
    anyone can create a server, invite the bot, and be an administrator
    of it in under a minute, so it admitted the entire internet.

    An empty BOT_OWNER_IDS refuses everybody rather than falling back to
    something broader. A misconfigured money printer should print nothing.
    """
    return bool(BOT_OWNER_IDS) and interaction.user.id in BOT_OWNER_IDS


@guild_decorator
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /grant
    # OWNER ONLY. Grants (or removes) any amount of any currency.
    @app_commands.command(
        name="grant",
        description="[Owner] Give a user any amount of any resource.",
    )
    @app_commands.describe(
        user="Who to give it to.",
        resource="Which currency.",
        amount="How much. Negative removes (never below zero).",
    )
    @app_commands.choices(resource=_CURRENCY_CHOICES)
    async def grant(self, ctx: discord.Interaction, user: discord.Member,
                    resource: str, amount: int):
        await responses.defer(ctx, ephemeral=True)

        # The gate is checked BEFORE anything else -- before the resource
        # is validated, before the player row is touched. A refusal must
        # not be distinguishable from a bad argument by timing or by
        # side-effect.
        if not _is_owner(ctx):
            logger.warning(
                "REFUSED /grant from %s (%s) -> %s %s %s",
                ctx.user, ctx.user.id, user.id, amount, resource)
            await responses.send(
                ctx, "That command isn't for you.", ephemeral=True)
            return

        if resource not in VALID_CURRENCIES:
            await responses.send(
                ctx, f"`{resource}` isn't a currency.", ephemeral=True)
            return
        if amount == 0:
            await responses.send(ctx, "Nothing to grant.", ephemeral=True)
            return
        if abs(amount) > MAX_GRANT:
            await responses.send(
                ctx,
                f"That's over the {MAX_GRANT:,} per-command cap. Run it twice "
                f"if you really mean it.",
                ephemeral=True)
            return

        db = SessionLocal()
        try:
            # get_or_create so a brand-new player can be stocked before
            # they have ever run /start.
            player = get_or_create_player(db, user.id, user.display_name)
            before = getattr(player, resource, 0) or 0

            if amount < 0:
                # add_currency is for adding. Removing is done here, with
                # an explicit floor -- a negative balance is not a state
                # any other part of the game is written to survive.
                after = max(0, before + amount)
                setattr(player, resource, after)
                db.commit()
            else:
                after = add_currency(db, player, resource, amount)

            logger.info(
                "GRANT by %s (%s): %s %+d -> %s (%s), %s -> %s",
                ctx.user, ctx.user.id, resource, amount,
                user.display_name, user.id, before, after)
        finally:
            db.close()

        verb = "Gave" if amount > 0 else "Removed"
        await ctx.followup.send(
            f"✅ {verb} {format_currency(resource, abs(amount))} "
            f"{'to' if amount > 0 else 'from'} {user.mention}.\n"
            f"Their balance: **{before:,} → {after:,}**",
            ephemeral=True,
        )


    # COMMAND: /takedown
    # OWNER ONLY. Unpublishes a dojo challenge.
    #
    # The dojo is the only system where one player's writing is shown to
    # another, so it is the only one that needs a way to remove something
    # a human has looked at and objected to. The character allowlist in
    # dojo_service stops formatting and mention abuse; it cannot stop a
    # name that is merely offensive, and no filter reliably can.
    #
    # It UNPUBLISHES rather than deletes, and sets removed_by_owner so
    # the author cannot simply republish it. The row survives so the
    # clears pointing at it survive too, and so there is a record of what
    # was removed.
    @app_commands.command(
        name="takedown",
        description="[Owner] Unpublish a dojo challenge by its share code.")
    @app_commands.describe(code="The challenge's share code.")
    async def takedown(self, ctx: discord.Interaction, code: str):
        await responses.defer(ctx, ephemeral=True)
        if not _is_owner(ctx):
            await responses.send(ctx, "That command isn't for you.", ephemeral=True)
            logger.info("TAKEDOWN refused for %s (%s)", ctx.user, ctx.user.id)
            return

        db = SessionLocal()
        try:
            from bot.services import dojo_service

            challenge = dojo_service.by_code(db, code)
            if challenge is None:
                await responses.send(ctx, f"No challenge with code `{code}`.",
                                     ephemeral=True)
                return
            dojo_service.take_down(db, challenge)
            logger.info("TAKEDOWN by %s (%s): %r (%s) by author %s",
                        ctx.user, ctx.user.id, challenge.name,
                        challenge.share_code, challenge.author_id)
            await responses.send(
                ctx,
                f"🚫 Removed **{challenge.name}** (`{challenge.share_code}`), "
                f"authored by <@{challenge.author_id}>. It can't be republished.",
                ephemeral=True)
        finally:
            db.close()


async def setup(bot):
    await bot.add_cog(Admin(bot))
