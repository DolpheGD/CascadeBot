"""
Shared "only the person who ran the command can use this menu" guard.

Two flavors, matching the two component patterns used across the cogs:

- OwnedView: base class for plain (non-DynamicItem) Views -- DungeonView,
  CombatView, ProfilePageView, etc. Stores the inviting user's
  Discord ID and blocks anyone else via interaction_check, which
  discord.py calls before dispatching to ANY child component, so
  individual buttons/selects don't need their own check. Every one of
  these views is freshly rebuilt from DB state on every real render in
  this codebase, so owner_id is always accurate for real usage; the one
  instance where it's intentionally None is the dummy copy registered
  once at bot startup purely for persistent custom_id routing (see
  bot/client.py) -- None disables the check so a stale message from
  before the most recent restart doesn't hard-lock everyone out before
  its next real render re-applies the owner.

- check_owner(): the equivalent one-line check for DynamicItems.
  DynamicItems carry their own state in their custom_id and get restored
  individually by regex after a restart (no shared parent view instance
  to hang interaction_check off of), so their custom_id templates embed
  the owner's Discord ID as another capture group and each callback calls
  this at the top instead.
"""

from __future__ import annotations

import discord

NOT_YOUR_MENU = "This isn't your menu -- run the command yourself to get your own."
NOT_STARTED = "You haven't started your journey yet. Use `/start` first."


async def require_player(interaction: discord.Interaction, player) -> bool:
    """The "have they run /start yet?" gate every player-facing command
    opens with. Returns True if `player` exists and the caller should
    carry on; otherwise sends the standard ephemeral nudge and returns
    False, so call sites read:

        player = get_player(db, ctx.user.id)
        if not await require_player(ctx, player):
            return

    This was an 18-times-copy-pasted `if player is None: await
    ctx.response.send_message(...)` block across seven cogs before, which
    is exactly how the wording drifts out of sync between commands.

    Works either side of a defer(): a command that had to defer first
    (because it makes a slow call before it can answer -- /vote hits
    top.gg) has already used up its initial response, so replying there
    has to go through followup instead."""
    if player is not None:
        return True
    if interaction.response.is_done():
        await interaction.followup.send(NOT_STARTED, ephemeral=True)
    else:
        await interaction.response.send_message(NOT_STARTED, ephemeral=True)
    return False


class OwnedView(discord.ui.View):
    def __init__(self, *args, owner_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is None or interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(NOT_YOUR_MENU, ephemeral=True)
        return False

    async def on_error(self, interaction: discord.Interaction,
                       error: Exception, item) -> None:
        """Every component in the bot inherits this, which is the point.

        discord.py's default is to log "Ignoring exception in view" and
        leave the interaction unanswered -- so a failed button looks
        identical to a button that did nothing, and the unanswered token
        drags the player's next few actions down with it. Routing it
        through responses.report_failure means the player always gets a
        sentence back, and the traceback still reaches the log.
        """
        from bot.utils import responses

        await responses.report_failure(
            interaction, error, where=f"{type(self).__name__}/{getattr(item, 'custom_id', item)}",
        )


async def check_owner(interaction: discord.Interaction, owner_id: int) -> bool:
    if interaction.user.id == owner_id:
        return True
    await interaction.response.send_message(NOT_YOUR_MENU, ephemeral=True)
    return False


def get_message_owner_id(interaction: discord.Interaction) -> int | None:
    """The Discord user who originally ran the slash command that produced
    the message a component is attached to. This is a property of the
    MESSAGE's origin (discord.py's InteractionMetadata, added 2.4) and
    correctly stays pointed at the original invoker even after the message
    has since been edited by follow-up component interactions -- exactly
    what DynamicItems need, since they're restored individually by
    custom_id regex (no shared parent View instance to hang
    interaction_check off after a restart) rather than dispatched through
    a persistent view instance the way OwnedView's children are.
    Returns None (fail open) if that metadata isn't available for some
    reason, rather than locking everyone out of an old message."""
    message = interaction.message
    if message is None:
        return None
    meta = getattr(message, "interaction_metadata", None) or getattr(message, "interaction", None)
    return meta.user.id if meta else None


async def check_message_owner(interaction: discord.Interaction) -> bool:
    owner_id = get_message_owner_id(interaction)
    if owner_id is None or interaction.user.id == owner_id:
        return True
    await interaction.response.send_message(NOT_YOUR_MENU, ephemeral=True)
    return False


async def require_feature(interaction: discord.Interaction, db, player, feature: str) -> bool:
    """The story gate. Returns True if the caller may use `feature`.

    Sibling of require_player above, and used the same way:

        if not await require_feature(ctx, db, player, "adventure"):
            return

    A locked feature is REFUSED WITH A REASON rather than hidden. A
    player who typed `/adventure` and got silence learns nothing; one who
    is told which mission opens it has something to do about it. See
    story_service.locked_message.

    Deliberately fails OPEN on any unexpected error: this sits in front
    of every gated command in the game, and a bug here locking someone
    out of content they own is a far worse outcome than a gate that
    briefly lets something through."""
    from bot.services import story_service

    try:
        if story_service.feature_unlocked(db, player, feature):
            return True
        message = story_service.locked_message(feature)
    except Exception:  # pragma: no cover - never lock someone out on a bug
        return True

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False
