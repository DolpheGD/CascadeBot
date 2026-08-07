"""
Account management, player-facing.

  /reset -- wipe your own account and start over, either CLEAN or with
      PRESTIGE (see bot/services/prestige_service.py for what prestige
      pays out and why it pays less than it costs).

----------------------------------------------------------------------
WHY THIS ISN'T /admin_reset ANY MORE
----------------------------------------------------------------------
Resetting used to be an admin command, on the reasoning that it is
irreversible and therefore dangerous. But the danger was never that the
wrong PERSON could run it -- it was already self-only, so an admin could
only ever delete their own save. All the restriction actually did was
stop ordinary players from starting over, which is a thing players
legitimately want to do, and which the game is explicitly built to
support: the prologue is the best content in it and there was no way to
see it twice.

So the gate moved from "who you are" to "did you mean it", which is what
the three-step confirmation below was always doing anyway.

----------------------------------------------------------------------
WHY THREE STEPS
----------------------------------------------------------------------
This is the only irreversible action in the bot, and the thing it
destroys is the thing its user cares most about. The confirmation is
designed to be impossible to clear by reflex:

  1. A PREVIEW that names what will die, with real row counts, and --
     for a prestige -- exactly what comes back. A prompt that asks "are
     you sure?" without saying what is at stake is a speed bump, not a
     confirmation.
  2. A TYPED CODE, regenerated per invocation. This is the step that
     matters: buttons get muscle-memoried and a fixed phrase can be
     pasted, but a code that exists only in the message in front of you
     cannot be typed without reading that message.
  3. A FINAL BUTTON, so the last act is deliberate and the typed code
     alone can't fire it.

Now that anyone can run it, the mode (clean vs prestige) is chosen at
step 1 and carried through, so the thing confirmed at step 3 is the
thing previewed at step 1 rather than whatever was clicked last.
"""

from __future__ import annotations

import secrets
import time

import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services import player_reset_service, prestige_service
from bot.services.currency_service import currency_emoji
from bot.services.player_service import get_player
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView

# How long a typed code stays valid. Long enough to read the preview
# properly, short enough that a forgotten prompt can't be cleared by
# someone who wandered back to it an hour later.
RESET_WINDOW_SECONDS = 120


class _PendingReset:
    """In memory, NOT in the database, on purpose: a pending reset should
    not survive a restart. The whole value of the confirmation is that
    the player is looking at the preview right now, and a token that
    outlives the process is one that can be confirmed against a preview
    nobody remembers reading."""

    def __init__(self, code: str, prestige: bool):
        self.code = code
        self.prestige = prestige
        self.created_at = time.monotonic()
        self.code_accepted = False

    def expired(self) -> bool:
        return time.monotonic() - self.created_at > RESET_WINDOW_SECONDS


_PENDING_RESETS: dict[int, _PendingReset] = {}


def _reward_lines(reward: prestige_service.PrestigeReward) -> str:
    parts = []
    if reward.gold:
        parts.append(f"{currency_emoji('gold')} **{reward.gold:,}** gold")
    if reward.shards:
        parts.append(f"{currency_emoji('shards')} **{reward.shards:,}** shards")
    for material, amount in reward.materials.items():
        parts.append(f"{currency_emoji(material)} **{amount:,}** {material.replace('_', ' ')}")
    for tier, count in reward.lootboxes.items():
        parts.append(f"🎁 **{count}×** {tier.title()} Lootbox")
    return "\n".join(parts) or "*Nothing — there's no progress to convert yet.*"


def _preview_embed(player, counts: dict[str, int], code: str,
                   can_prestige: bool, reason: str,
                   reward: prestige_service.PrestigeReward) -> discord.Embed:
    """Step 1: what is about to be destroyed, and what (if anything)
    comes back."""
    embed = discord.Embed(
        title="⚠️ Start over?",
        description=(
            f"This wipes **{player.username}** completely — characters, gear, story "
            f"progress, base, research and currency. **There is no undo and no backup.**\n\n"
            f"You'll be dropped straight back into the prologue afterwards; you do "
            f"**not** need to run `/start` again."
        ),
        color=discord.Color.red(),
    )
    if counts:
        rows = "\n".join(f"`{count:>5}`  {name}" for name, count in
                         sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        embed.add_field(name=f"Rows to delete ({sum(counts.values())} total)",
                        value=rows[:1024], inline=False)

    embed.add_field(
        name="🧹 Clean reset",
        value="Everything goes. You start exactly as a brand new player would.",
        inline=False,
    )
    if can_prestige:
        embed.add_field(
            name=f"🔆 Prestige reset — progress score {reward.score:,}",
            value=(
                f"The same wipe, but you keep a prestige badge and start with:\n"
                f"{_reward_lines(reward)}\n\n"
                f"*Worth deliberately less than the run it replaces — prestige buys a "
                f"head start, not a profit.*"
            ),
            inline=False,
        )
    else:
        embed.add_field(name="🔆 Prestige reset — locked", value=reason, inline=False)

    embed.add_field(
        name="Step 1 of 3 — pick how you want to reset",
        value=("Choose below, then type this code when asked:\n"
               f"# `{code}`\n"
               f"*Expires in {RESET_WINDOW_SECONDS // 60} minutes.*"),
        inline=False,
    )
    return embed


@guild_decorator
class Account(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /reset
    #
    # Open to everyone. See the module docstring for why this stopped
    # being an admin command, and why it still takes three steps.
    @app_commands.command(
        name="reset",
        description="Wipe your account and start over — cleanly, or with prestige rewards.",
    )
    async def reset(self, ctx: discord.Interaction):
        await responses.defer(ctx, ephemeral=True)

        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await responses.send(
                    ctx, "You have no account to reset — `/start` hasn't been run.",
                    ephemeral=True,
                )
                return
            counts = player_reset_service.preview(db, ctx.user.id)
            can_prestige, reason = prestige_service.eligible(db, player)
            reward = prestige_service.preview_rewards(db, player)
            embed = _preview_embed(player, counts, "", can_prestige, reason, reward)
        finally:
            db.close()

        code = secrets.token_hex(2).upper()
        # Built once above with a placeholder so the DB session is closed
        # before any Discord I/O; the code is the only late-bound part.
        embed.set_field_at(
            len(embed.fields) - 1,
            name="Step 1 of 3 — pick how you want to reset",
            value=("Choose below, then type this code when asked:\n"
                   f"# `{code}`\n"
                   f"*Expires in {RESET_WINDOW_SECONDS // 60} minutes.*"),
            inline=False,
        )
        _PENDING_RESETS[ctx.user.id] = _PendingReset(code=code, prestige=False)

        await responses.send(
            ctx, embed=embed,
            view=_ResetChoiceView(owner_id=ctx.user.id, can_prestige=can_prestige),
            ephemeral=True,
        )


class _ResetChoiceView(OwnedView):
    """Step 1 -> step 2, and the place the MODE is chosen.

    Deliberately not persistent (its timeout is the reset window), so a
    stale prompt from an earlier session can't be revived by clicking an
    old message."""

    def __init__(self, owner_id: int, can_prestige: bool):
        super().__init__(timeout=RESET_WINDOW_SECONDS, owner_id=owner_id)
        if not can_prestige:
            # Present but disabled, rather than absent: a player who has
            # heard prestige exists should be able to see the button and
            # read why it isn't available, instead of wondering whether
            # their version has it.
            self.prestige_reset.disabled = True

    async def _begin(self, interaction: discord.Interaction, prestige: bool):
        pending = _PENDING_RESETS.get(interaction.user.id)
        if pending is None or pending.expired():
            _PENDING_RESETS.pop(interaction.user.id, None)
            await responses.edit(
                interaction, content="That reset prompt expired. Run `/reset` again.",
                embed=None, view=None,
            )
            return
        pending.prestige = prestige
        await interaction.response.send_modal(_ResetCodeModal(pending))

    @discord.ui.button(label="🧹 Clean reset", style=discord.ButtonStyle.danger)
    async def clean_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._begin(interaction, prestige=False)

    @discord.ui.button(label="🔆 Prestige reset", style=discord.ButtonStyle.primary)
    async def prestige_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._begin(interaction, prestige=True)

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
    memory or muscle memory."""

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
                interaction, "That reset prompt expired. Run `/reset` again.", ephemeral=True,
            )
            return
        if self.code_input.value.strip().upper() != self._pending.code:
            await responses.send(
                interaction,
                f"That code doesn't match (expected `{self._pending.code}`). "
                f"Nothing was deleted — run `/reset` again if you meant to.",
                ephemeral=True,
            )
            return

        self._pending.code_accepted = True
        mode = "prestige reset" if self._pending.prestige else "clean reset"
        embed = discord.Embed(
            title="⚠️ Last chance",
            description=(
                f"Code accepted for a **{mode}**. Pressing the button below wipes your "
                f"account **immediately and permanently.**"
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

    @discord.ui.button(label="Wipe my account", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await responses.defer(interaction, ephemeral=True)
        pending = _PENDING_RESETS.get(interaction.user.id)
        # Re-checked here rather than trusted from step 2: this callback
        # is reachable directly by anyone who kept the message around,
        # and "the code was accepted at some point" is not the same claim
        # as "this confirmation is still live".
        if pending is None or pending.expired() or not pending.code_accepted:
            _PENDING_RESETS.pop(interaction.user.id, None)
            await responses.edit(
                interaction, content="That confirmation is no longer valid. Nothing was deleted.",
                embed=None, view=None,
            )
            return

        prestige = pending.prestige
        _PENDING_RESETS.pop(interaction.user.id, None)

        db = SessionLocal()
        try:
            deleted, reward = prestige_service.perform(db, interaction.user.id, prestige)
            player = get_player(db, interaction.user.id)
            badges = prestige_service.badge_text(player) if player else ""
        finally:
            db.close()

        total = sum(deleted.values())
        if prestige:
            embed = discord.Embed(
                title=f"🔆 Prestiged {badges}",
                description=(
                    f"Wiped **{total}** rows across {len(deleted)} tables, and started you "
                    f"again with your prestige bundle.\n\nUse **`/story`** to begin."
                ),
                color=discord.Color.gold(),
            )
            embed.add_field(name="Granted", value=_reward_lines(reward)[:1024], inline=False)
        else:
            embed = discord.Embed(
                title="🧹 Account reset",
                description=(
                    f"Removed **{total}** rows across {len(deleted)} tables. Your account has "
                    f"been recreated empty.\n\nUse **`/story`** to begin."
                ),
                color=discord.Color.greyple(),
            )
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
    await bot.add_cog(Account(bot))
