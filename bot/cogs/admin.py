"""
Admin/dev tooling.

  /admin_boosterkit -- grants a specified user a pile of currency and
      starter lootboxes. Meant for onboarding/compensation, not full
      gear-testing setup, so it works on anyone regardless of whether
      they've run /start yet.

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

from bot.config import ADMIN_USER_IDS, BOT_OWNER_IDS
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services import lootbox_service
from bot.services.currency_service import (
    VALID_CURRENCIES, add_currency, currency_emoji, format_currency,
)
from bot.utils.logger import get_logger
from bot.services.player_service import get_or_create_player
from bot.utils.guild_decorator import guild_decorator

logger = get_logger(__name__)

BOOSTER_GOLD = 10000
BOOSTER_SHARDS = 1000
BOOSTER_LOOTBOXES_PER_TIER = 5
BOOSTER_LOOTBOX_TIERS = ("common", "uncommon", "rare", "epic")

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


def _is_admin(interaction: discord.Interaction) -> bool:
    """Bot admins, OR anyone with Discord Administrator here.

    Deliberately broad, and only ever used for /admin_boosterkit, which
    hands out a fixed modest bundle. See _is_owner for why anything that
    creates arbitrary currency must not use this gate.
    """
    if interaction.user.id in ADMIN_USER_IDS:
        return True
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def _is_owner(interaction: discord.Interaction) -> bool:
    """The bot owner, and nobody else. No fallback, ever.

    NOT _is_admin. That helper also accepts anyone holding Discord's
    "Administrator" permission in whatever server the command was typed
    in -- and anyone at all can create a server, invite the bot, and be
    an administrator of it in under a minute. For a fixed booster kit
    that is an acceptable trade; for /grant, which mints unlimited
    currency, it would mean the economy has no owner.

    An empty BOT_OWNER_IDS refuses everybody rather than falling back to
    something broader. A misconfigured money printer should print nothing.
    """
    return bool(BOT_OWNER_IDS) and interaction.user.id in BOT_OWNER_IDS


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
        await responses.defer(ctx, ephemeral=True)
        if not _is_admin(ctx):
            await responses.send(ctx,
                "You need Administrator permission (or be a configured bot admin) to use this.",
                ephemeral=True,
            )
            return

        db = SessionLocal()
        try:
            player = get_or_create_player(db, user.id, user.display_name)

            # ONCE PER PLAYER.
            #
            # _is_admin accepts anyone with Discord's Administrator
            # permission in whatever server the command was typed in, and
            # anyone can create a server and invite the bot. Without this
            # check that made a repeatable 1,000-shard / 10,000-gold /
            # 20-lootbox faucet available to effectively anybody -- about
            # eight gacha pulls per invocation, unlimited invocations.
            #
            # Capping it at one keeps the stated purpose (onboarding and
            # compensation) intact and closes the faucet. An owner who
            # genuinely needs to hand out more has /grant, which is gated
            # on BOT_OWNER_IDS.
            if player.booster_kit_claimed:
                await responses.send(
                    ctx,
                    f"{user.mention} has already had a booster kit. "
                    f"Use `/grant` if you need to give them more.",
                    ephemeral=True)
                return

            add_currency(db, player, "gold", BOOSTER_GOLD)
            add_currency(db, player, "shards", BOOSTER_SHARDS)

            for tier in BOOSTER_LOOTBOX_TIERS:
                lootbox_service.grant_lootbox(db, player, tier, BOOSTER_LOOTBOXES_PER_TIER)

            player.booster_kit_claimed = True
            logger.info("BOOSTERKIT by %s (%s) -> %s (%s)",
                        ctx.user, ctx.user.id, user.display_name, user.id)
            db.commit()
        finally:
            db.close()

        summary = (
            f"🎁 **Booster kit granted to {user.mention}!**\n"
            f"🪙 +{BOOSTER_GOLD:,} gold | {currency_emoji('shards')} +{BOOSTER_SHARDS:,} shards\n"
            f"📦 +{BOOSTER_LOOTBOXES_PER_TIER} of each: "
            + ", ".join(tier.title() for tier in BOOSTER_LOOTBOX_TIERS) + " lootbox"
        )
        await ctx.followup.send(summary, ephemeral=True)


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


async def setup(bot):
    await bot.add_cog(Admin(bot))
