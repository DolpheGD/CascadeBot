"""
Dungeon encounters embeds.

Interactive NPC encounters (bot/game/dungeon/encounter_config.py).
"""

from __future__ import annotations

import discord

from bot.services.currency_service import format_currency


# ----------------------------------------------------------------------
# Interactive dungeon rooms: Encounter
#
# Trap and Puzzle rooms no longer have bespoke embeds -- every non-combat
# room type resolves through the Encounter system now (see
# bot/game/dungeon/encounter_config.py), so trap_embed/puzzle_embed were
# removed along with the TRAP_CHOICES/PUZZLES tables they rendered.
# ----------------------------------------------------------------------

def encounter_embed(node: dict, encounter: dict, message: str | None = None, player=None) -> discord.Embed:
    """Story-room NPC encounters (bot/game/dungeon/encounter_config.py) --
    unlike a plain fallback room, these carry their own flavor art (ported
    from the old JS bot's explore.js `imageUrl` fields), rendered full-size
    via set_image rather than as the usual avatar set_thumbnail.

    `player` is optional (only needed to show "you have" holdings) so
    this still works anywhere it's called without one on hand."""
    embed = discord.Embed(
        title=f"📜 {encounter['name']} -- Floor {node['floor']}",
        description=message or "",
        color=discord.Color.dark_purple(),
    )
    for choice in encounter["choices"]:
        value = choice["description"] or "\u200b"
        cost = choice.get("cost")
        if player is not None and cost:
            holdings = ", ".join(format_currency(currency, getattr(player, currency, 0)) for currency in cost)
            value = f"{value}\nYou have: {holdings}" if value != "\u200b" else f"You have: {holdings}"
        embed.add_field(name=choice["label"], value=value, inline=False)
    image_url = encounter.get("image_url")
    if image_url:
        embed.set_image(url=image_url)
    return embed
