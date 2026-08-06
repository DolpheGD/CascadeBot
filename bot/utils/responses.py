"""
Interaction replies that survive a slow database and a dead token.

----------------------------------------------------------------------
THE 3-SECOND RULE, AND WHY IT KEPT BEING BROKEN
----------------------------------------------------------------------
Discord gives a bot THREE SECONDS to make the first response to an
interaction. Miss it and the token is dead: every later call against it
returns 404 Unknown interaction (error code 10062), and there is no way
to reply at all -- the player sees "the application did not respond".

Every command in this bot opens a SQLAlchemy session and does its
queries synchronously, on the event loop. That is fine in isolation --
SQLite answers in milliseconds -- but it is not fine under contention:
SQLite takes a database-wide write lock, so any command that wants to
read while an expedition, a raid attack or a harvester collection is
committing simply BLOCKS the whole loop until that writer is done. Add a
gateway reconnect (the token is already a second or two old by the time
the command is dispatched) and the budget is gone before the handler has
done anything wrong.

Observed as four separate crashes on one evening -- /gift, /squad, and
the inventory paginator -- with no common code path except that all of
them queried the database before answering.

----------------------------------------------------------------------
THE FIX IS TWO HALVES, AND BOTH ARE NEEDED
----------------------------------------------------------------------
1. DEFER FIRST. `defer()` is itself a valid first response, so calling
   it before any database work converts the 3-second budget into a
   15-minute one. After deferring, replies must go through `followup`
   instead of `response` -- which is exactly the branch `send()` below
   hides, so call sites don't have to care whether they deferred.

2. NEVER CRASH ON A DEAD TOKEN. Deferring makes expiry far less likely,
   not impossible: if the process is wedged for three seconds before the
   handler is even entered, nothing can save the reply. When that
   happens the right behaviour is a single log line, not a traceback --
   there is no user-visible difference (the reply was never going to
   arrive) and the traceback buries real bugs in noise. So every helper
   here swallows 10062, and only 10062.

Nothing else is swallowed. A 403, a 50035 malformed-embed, or a bug in
the handler still raises loudly, because those are all fixable and all
mean the code is wrong.
"""

from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)

# Unknown interaction: the token expired (or was already consumed) and
# no reply can ever be delivered through it.
UNKNOWN_INTERACTION = 10062

# Interaction has already been acknowledged. Raised when something
# defers twice -- harmless, and the second caller's intent is already
# satisfied, so it's treated the same as success.
ALREADY_ACKNOWLEDGED = 40060


def _is_expired(error: discord.HTTPException) -> bool:
    return getattr(error, "code", None) in (UNKNOWN_INTERACTION, ALREADY_ACKNOWLEDGED)


def _describe(interaction: discord.Interaction) -> str:
    if interaction.command is not None:
        return f"/{interaction.command.qualified_name}"
    return f"component on {interaction.channel_id}"


async def defer(interaction: discord.Interaction, *, ephemeral: bool = False) -> bool:
    """Acknowledge the interaction NOW, buying 15 minutes to answer it.

    Call this as the first line of any handler that touches the database
    -- before opening the session, not after. Returns False if the token
    was already dead on arrival, which lets a handler skip work nobody
    will ever see.

    `ephemeral` has to match how the command finally replies: it decides
    whether the "thinking..." placeholder, and the message that replaces
    it, are private. Commands whose main reply is public pass False even
    though their error paths are ephemeral -- an ephemeral followup after
    a public defer is allowed, and that combination is what nearly every
    command here wants.
    """
    if interaction.response.is_done():
        return True
    try:
        await interaction.response.defer(ephemeral=ephemeral)
        return True
    except discord.HTTPException as error:
        if _is_expired(error):
            log.warning("interaction expired before %s could defer", _describe(interaction))
            return False
        raise


async def send(interaction: discord.Interaction, *args, **kwargs) -> None:
    """Reply, whether or not the interaction was deferred.

    This is the single reason call sites can defer freely: after a defer
    (or any earlier reply) the response slot is spent and Discord
    requires `followup.send`; before one, it requires
    `response.send_message`. Picking the wrong one is a runtime error,
    and picking it correctly by hand means every handler has to track
    its own reply state.
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(*args, **kwargs)
        else:
            await interaction.response.send_message(*args, **kwargs)
    except discord.HTTPException as error:
        if _is_expired(error):
            log.warning("interaction expired before %s could reply", _describe(interaction))
            return
        raise


async def edit(interaction: discord.Interaction, *args, **kwargs) -> None:
    """Edit the message a COMPONENT is attached to.

    Same defer-awareness as send(): once deferred, the original message
    is reached through edit_original_response rather than
    response.edit_message.
    """
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(*args, **kwargs)
        else:
            await interaction.response.edit_message(*args, **kwargs)
    except discord.HTTPException as error:
        if _is_expired(error):
            log.warning("interaction expired before %s could edit", _describe(interaction))
            return
        raise
