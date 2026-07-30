"""
Dungeon map embeds.

The room-choice / floor map embed for an active expedition.
"""

from __future__ import annotations

import discord

from bot.utils.embedder._shared import ROOM_TYPE_EMOJI


# ----------------------------------------------------------------------
# Dungeon map
# ----------------------------------------------------------------------

def dungeon_map_embed(
    expedition, message: str | None = None, avatar_url: str | None = None,
    squad_hp_lines: list[str] | None = None,
) -> discord.Embed:
    """Shows the current node and, if given, a one-line result of what just
    happened (e.g. 'You find a treasure chest...'). `squad_hp_lines` --
    build with cogs.dungeon._squad_hp_lines() -- shows each squad member's
    actual persisted HP instead of a flat, always-100 placeholder."""
    from bot.game.dungeon.region_config import get_region_difficulty

    node = expedition.graph["nodes"][expedition.current_node_id]
    emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")
    difficulty = get_region_difficulty(expedition.region)

    num_floors = expedition.graph.get("num_floors", node["floor"] + 1)
    boss_nodes = expedition.graph.get("boss_nodes", [expedition.graph.get("boss_node")])
    bosses_cleared = sum(
        1 for b in boss_nodes if expedition.graph["nodes"].get(b, {}).get("completed")
    )

    embed = discord.Embed(
        title=f"{expedition.region} ({difficulty['difficulty_label']}) -- Floor {node['floor']}/{num_floors - 1}",
        description=message or "",
        color=discord.Color.dark_green(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="Current Room", value=f"{emoji} {node['room_type'].title()}", inline=True)
    embed.add_field(name="👹 Bosses", value=f"{bosses_cleared}/{len(boss_nodes)} defeated", inline=True)
    if squad_hp_lines:
        embed.add_field(name="❤️ Squad HP", value="\n".join(squad_hp_lines), inline=True)

    if expedition.status.value == "completed":
        embed.add_field(name="Status", value="🏆 Expedition Complete!", inline=False)
    elif expedition.status.value == "failed":
        embed.add_field(name="Status", value="💀 Expedition Failed", inline=False)
    else:
        moves = node["edges"]
        if moves:
            options = "\n".join(
                f"{ROOM_TYPE_EMOJI.get(expedition.graph['nodes'][n]['room_type'], '❔')} "
                f"{expedition.graph['nodes'][n]['room_type'].title()} (Floor {expedition.graph['nodes'][n]['floor']})"
                for n in moves
            )
            embed.add_field(name=f"🗺️ Paths Ahead ({len(moves)} options)", value=options, inline=False)

    return embed
