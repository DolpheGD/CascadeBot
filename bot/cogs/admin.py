"""
Admin/dev tooling.

  /admin_boosterkit -- grants a specified user a pile of currency and
      starter lootboxes. Meant for onboarding/compensation, not full
      gear-testing setup, so it works on anyone regardless of whether
      they've run /start yet.

  /admin_reset -- deletes YOUR OWN account so the first-run experience
      can be replayed. Self-only and irreversible; see the confirmation
      notes further down for why it takes three steps to fire.
"""

from __future__ import annotations

import secrets
import time

import discord

from discord.ext import commands
from discord import app_commands

from bot.config import ADMIN_USER_IDS
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services import lootbox_service, player_reset_service
from bot.services.currency_service import add_currency
from bot.services.player_service import get_or_create_player, get_player
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView

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

            add_currency(db, player, "gold", BOOSTER_GOLD)
            add_currency(db, player, "shards", BOOSTER_SHARDS)

            for tier in BOOSTER_LOOTBOX_TIERS:
                lootbox_service.grant_lootbox(db, player, tier, BOOSTER_LOOTBOXES_PER_TIER)

            db.commit()
        finally:
            db.close()

        summary = (
            f"🎁 **Booster kit granted to {user.mention}!**\n"
            f"🪙 +{BOOSTER_GOLD:,} gold | <:shard:1534383382924890192> +{BOOSTER_SHARDS:,} shards\n"
            f"📦 +{BOOSTER_LOOTBOXES_PER_TIER} of each: "
            + ", ".join(tier.title() for tier in BOOSTER_LOOTBOX_TIERS) + " lootbox"
        )
        await ctx.followup.send(summary, ephemeral=True)

    # COMMAND: /admin_reset
    #
    # Deletes the CALLER'S OWN account, so the prologue and the whole
    # first-run experience can be replayed without hand-editing the
    # database or making a second Discord account.
    #
    # ------------------------------------------------------------------
    # WHY THREE STEPS
    # ------------------------------------------------------------------
    # This is the only irreversible command in the bot, and the thing it
    # destroys is the thing its user cares most about. The confirmation
    # is therefore designed to be impossible to clear by reflex:
    #
    #   1. A PREVIEW that names what will die, with real row counts. A
    #      prompt that asks "are you sure?" without saying what is at
    #      stake is not a confirmation, it's a speed bump.
    #   2. A TYPED PHRASE containing a per-invocation random token. This
    #      is the step that matters: buttons can be muscle-memoried and
    #      a fixed phrase can be pasted, but a code that only exists in
    #      the message in front of you cannot be typed without reading
    #      that message.
    #   3. A FINAL BUTTON, so the last act is deliberate and the typed
    #      code alone can't fire it.
    #
    # Self-only by design. An optional `user` argument would make this
    # more convenient and would also mean one mistyped autocomplete
    # destroys a real player's save with no undo. Convenience is not
    # worth that; a second test account is cheap.
    @app_commands.command(
        name="admin_reset",
        description="[Admin] Permanently delete YOUR OWN account so you can start over. Irreversible.",
    )
    async def admin_reset(self, ctx: discord.Interaction):
        await responses.defer(ctx, ephemeral=True)
        if not _is_admin(ctx):
            await responses.send(
                ctx,
                "You need Administrator permission (or be a configured bot admin) to use this.",
                ephemeral=True,
            )
            return

        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await responses.send(
                    ctx, "You have no account to reset -- `/start` hasn't been run.",
                    ephemeral=True,
                )
                return
            counts = player_reset_service.preview(db, ctx.user.id)
            username = player.username
        finally:
            db.close()

        code = secrets.token_hex(2).upper()
        _PENDING_RESETS[ctx.user.id] = _PendingReset(code=code)

        await responses.send(
            ctx, embed=_reset_preview_embed(username, counts, code),
            view=_ResetConfirmView(owner_id=ctx.user.id), ephemeral=True,
        )


# ----------------------------------------------------------------------
# Reset confirmation state.
#
# Held in memory rather than the database on purpose: a pending reset
# SHOULD NOT survive a restart. The whole value of the confirmation is
# that the player is looking at the preview right now, and a token that
# outlives the process is one that can be confirmed against a preview
# nobody remembers reading.
# ----------------------------------------------------------------------

# How long a typed code stays valid. Long enough to read the preview
# properly, short enough that a forgotten prompt can't be cleared by
# someone who wandered back an hour later.
RESET_WINDOW_SECONDS = 120


class _PendingReset:
    def __init__(self, code: str):
        self.code = code
        self.created_at = time.monotonic()
        self.code_accepted = False

    def expired(self) -> bool:
        return time.monotonic() - self.created_at > RESET_WINDOW_SECONDS


_PENDING_RESETS: dict[int, _PendingReset] = {}


def _reset_preview_embed(username: str, counts: dict[str, int], code: str) -> discord.Embed:
    """Step 1: what is about to be destroyed, itemised."""
    embed = discord.Embed(
        title="⚠️ Permanently delete your account?",
        description=(
            f"This wipes **{username}** completely -- characters, gear, story progress, "
            f"base, research and currency. **There is no undo and no backup.**\n\n"
            f"Afterwards `/start` will treat you as a brand new player, which is the "
            f"point: it's how you replay the prologue."
        ),
        color=discord.Color.red(),
    )
    if counts:
        rows = "\n".join(f"`{count:>5}`  {name}" for name, count in
                         sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        embed.add_field(name=f"Rows to delete ({sum(counts.values())} total)",
                        value=rows[:1024], inline=False)
    embed.add_field(
        name="Step 1 of 3 -- confirm you've read this",
        value=("Press **I understand** below, then type this code when asked:\n"
               f"# `{code}`\n"
               f"*Expires in {RESET_WINDOW_SECONDS // 60} minutes.*"),
        inline=False,
    )
    return embed


class _ResetConfirmView(OwnedView):
    """Step 1 -> step 2. Deliberately NOT persistent (timeout is the
    reset window), so a stale prompt from an earlier session can't be
    revived by clicking an old message."""

    def __init__(self, owner_id: int):
        super().__init__(timeout=RESET_WINDOW_SECONDS, owner_id=owner_id)

    @discord.ui.button(label="I understand", style=discord.ButtonStyle.danger)
    async def understood(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending = _PENDING_RESETS.get(interaction.user.id)
        if pending is None or pending.expired():
            _PENDING_RESETS.pop(interaction.user.id, None)
            await responses.edit(
                interaction, content="That reset prompt expired. Run `/admin_reset` again.",
                embed=None, view=None,
            )
            return
        await interaction.response.send_modal(_ResetCodeModal(pending))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        _PENDING_RESETS.pop(interaction.user.id, None)
        await responses.edit(
            interaction, content="Cancelled. Nothing was deleted.", embed=None, view=None,
        )


class _ResetCodeModal(discord.ui.Modal, title="Type the code to continue"):
    """Step 2: the code from the preview, typed by hand.

    A modal rather than another button because this step has to cost
    ATTENTION, not just a click. The code is regenerated per invocation
    and appears only in the message above, so it cannot be typed from
    memory or muscle memory.
    """

    code_input = discord.ui.TextInput(
        label="Confirmation code", placeholder="The code shown above",
        min_length=4, max_length=4, required=True,
    )

    def __init__(self, pending: _PendingReset):
        super().__init__()
        self._pending = pending

    async def on_submit(self, interaction: discord.Interaction):
        if self._pending.expired():
            _PENDING_RESETS.pop(interaction.user.id, None)
            await responses.send(
                interaction, "That reset prompt expired. Run `/admin_reset` again.",
                ephemeral=True,
            )
            return
        if self.code_input.value.strip().upper() != self._pending.code:
            await responses.send(
                interaction,
                f"That code doesn't match (expected `{self._pending.code}`). "
                f"Nothing was deleted -- run `/admin_reset` again if you meant to.",
                ephemeral=True,
            )
            return

        self._pending.code_accepted = True
        embed = discord.Embed(
            title="⚠️ Last chance",
            description=(
                "Code accepted. Pressing the button below deletes your account "
                "**immediately and permanently.**"
            ),
            color=discord.Color.red(),
        )
        await responses.send(
            interaction, embed=embed,
            view=_ResetFinalView(owner_id=interaction.user.id), ephemeral=True,
        )


class _ResetFinalView(OwnedView):
    """Step 3: the irreversible one."""

    def __init__(self, owner_id: int):
        super().__init__(timeout=RESET_WINDOW_SECONDS, owner_id=owner_id)

    @discord.ui.button(label="Delete my account forever", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await responses.defer(interaction, ephemeral=True)
        pending = _PENDING_RESETS.get(interaction.user.id)
        # Re-checked here rather than trusted from step 2: this callback
        # is reachable directly by anyone who kept the message around,
        # and "the code was accepted at some point" is not the same
        # claim as "this confirmation is still live".
        if pending is None or pending.expired() or not pending.code_accepted:
            _PENDING_RESETS.pop(interaction.user.id, None)
            await responses.edit(
                interaction, content="That confirmation is no longer valid. Nothing was deleted.",
                embed=None, view=None,
            )
            return

        _PENDING_RESETS.pop(interaction.user.id, None)
        db = SessionLocal()
        try:
            deleted = player_reset_service.reset(db, interaction.user.id)
        finally:
            db.close()

        total = sum(deleted.values())
        summary = "\n".join(f"`{count:>5}`  {name}" for name, count in sorted(deleted.items()))
        embed = discord.Embed(
            title="🧹 Account deleted",
            description=f"Removed **{total}** rows across {len(deleted)} tables.\n\n"
                        f"Run `/start` to begin again.",
            color=discord.Color.greyple(),
        )
        if summary:
            embed.add_field(name="Deleted", value=summary[:1024], inline=False)
        # EDIT rather than send: this replaces the "Last chance" prompt,
        # which takes its still-live buttons off the screen with it. A
        # followup would leave a spent confirmation sitting above the
        # result, inviting a second click on a reset that already ran.
        await responses.edit(interaction, content=None, embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        _PENDING_RESETS.pop(interaction.user.id, None)
        await responses.edit(
            interaction, content="Cancelled. Nothing was deleted.", embed=None, view=None,
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
