"""
Relic and campfire embeds.

Run-scoped relics (bot/game/dungeon/relic_config.py) and the Rest-or-Attune
campfire that's the main way to get them.
"""

from __future__ import annotations

import discord

from bot.game.dungeon.relic_config import CAMPFIRE_REST_PERCENT, RARITY_EMOJI, format_relic

CAMPFIRE_COLOR = discord.Color.orange()
RELIC_COLOR = discord.Color.from_rgb(186, 142, 255)


def relic_lines(relics: list[dict]) -> str:
    """Compact one-per-line listing of held relics, reused by the dungeon
    map, the campfire screen and the end-of-run summary so the three can
    never disagree about how a relic is named or described."""
    if not relics:
        return "*None yet.*"
    return "\n".join(
        f"{r['emoji']} **{r['name']}** {RARITY_EMOJI.get(r['rarity'], '')} -- {r['description']}"
        for r in relics
    )


def campfire_embed(node: dict, offer: list[dict], held: list[dict], message: str | None = None) -> discord.Embed:
    """The campfire choice: Rest or Attune, one only.

    Both options are laid out in full BEFORE the player picks, including
    the exact relics on offer -- the decision is the content here, so
    hiding either side of it behind a click would just be friction."""
    embed = discord.Embed(
        title=f"🏕️ Campfire -- Floor {node['floor']}",
        description=message or "There's time for one thing only before the boss.",
        color=CAMPFIRE_COLOR,
    )

    embed.add_field(
        name=f"🔥 Rest -- recover {CAMPFIRE_REST_PERCENT}% HP",
        value="Heal the whole squad. No relic.",
        inline=False,
    )

    if offer:
        embed.add_field(
            name="✨ Attune -- take one relic",
            value="\n\n".join(format_relic(r) for r in offer) + "\n\n*No healing if you attune.*",
            inline=False,
        )
    else:
        embed.add_field(
            name="✨ Attune",
            value="*You already carry every relic this world has to offer.*",
            inline=False,
        )

    if held:
        embed.add_field(name="🎒 Relics carried", value=relic_lines(held), inline=False)

    embed.set_footer(text="Relics last until this expedition ends.")
    return embed


def relic_gained_embed(relic: dict, held: list[dict]) -> discord.Embed:
    """Shown when a relic drops from an elite or a non-final boss."""
    embed = discord.Embed(
        title="✨ Relic acquired!",
        description=format_relic(relic),
        color=RELIC_COLOR,
    )
    if len(held) > 1:
        embed.add_field(name="🎒 Relics carried", value=relic_lines(held), inline=False)
    embed.set_footer(text="Relics last until this expedition ends.")
    return embed
