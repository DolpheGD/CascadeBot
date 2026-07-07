import discord


ROOM_TYPE_EMOJI = {
    "start": "🚪", "combat": "⚔️", "elite": "🔥", "treasure": "💰",
    "merchant": "🛒", "campfire": "🏕️", "story": "📜", "trap": "⚠️",
    "shrine": "⛩️", "puzzle": "🧩", "secret": "❓", "boss": "💀",
}


async def profile_embed(player):
    """
    returns a discord embed showing a player's profile stats
    """
    embed = discord.Embed(
        title=f"{player.username}'s Profile",
        color=discord.Color.blurple(),
    )

    embed.add_field(name="Class", value=player.class_name)
    embed.add_field(name="Level", value=str(player.level))
    embed.add_field(name="XP", value=f"{player.xp} / {player.xp_to_next_level()}")
    embed.add_field(name="Gold", value=str(player.gold))
    embed.add_field(name="Reputation", value=str(player.reputation))
    embed.add_field(
        name="Stats",
        value=(
            f"HP: {player.max_hp} | ATK: {player.attack} | DEF: {player.defense}\n"
            f"MAG: {player.magic} | SPD: {player.speed} | LUCK: {player.luck}\n"
            f"Crit: {player.crit_chance}% | Dodge: {player.dodge}%"
        ),
        inline=False,
    )

    return embed


def _bar(current: float, maximum: float, length: int = 10) -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = max(0, min(length, round(length * current / maximum)))
    return "█" * filled + "░" * (length - filled)


def dungeon_map_embed(expedition, message: str | None = None) -> discord.Embed:
    """Shows the current node and, if given, a one-line result of what just
    happened (e.g. 'You find a treasure chest...')."""
    node = expedition.graph["nodes"][expedition.current_node_id]
    emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")

    embed = discord.Embed(
        title=f"{expedition.region} -- Floor {node['floor']}",
        description=message or "",
        color=discord.Color.dark_green(),
    )
    embed.add_field(
        name="Current Room",
        value=f"{emoji} {node['room_type'].title()}",
        inline=True,
    )
    embed.add_field(name="HP", value=f"{expedition.current_hp}", inline=True)

    if expedition.status.value == "completed":
        embed.add_field(name="Status", value="🏆 Expedition Complete!", inline=False)
    elif expedition.status.value == "failed":
        embed.add_field(name="Status", value="💀 Expedition Failed", inline=False)
    else:
        moves = node["edges"]
        if moves:
            options = ", ".join(
                f"{ROOM_TYPE_EMOJI.get(expedition.graph['nodes'][n]['room_type'], '❔')} "
                f"{expedition.graph['nodes'][n]['room_type'].title()}"
                for n in moves
            )
            embed.add_field(name="Paths Ahead", value=options, inline=False)

    return embed


def combat_embed(battle) -> discord.Embed:
    """Renders the current battle state: HP/resource bars for everyone and
    the last few log lines, so a Discord message can be edited in place
    turn after turn."""
    color = discord.Color.red()
    if battle.result == "won":
        color = discord.Color.gold()
    elif battle.result == "lost":
        color = discord.Color.dark_gray()
    elif battle.result == "fled":
        color = discord.Color.orange()

    embed = discord.Embed(title="Battle!", color=color)

    player = battle.player
    player_value = (
        f"HP: {player.current_hp}/{player.max_hp} {_bar(player.current_hp, player.max_hp)}\n"
        f"MP: {player.mana}/{player.max_mana} | EN: {player.energy}/{player.max_energy}"
    )
    embed.add_field(name=f"🧑 {player.name}", value=player_value, inline=False)

    for enemy in battle.enemies:
        status = "💀 Defeated" if not enemy.is_alive() else (
            f"HP: {enemy.current_hp}/{enemy.max_hp} {_bar(enemy.current_hp, enemy.max_hp)}"
        )
        embed.add_field(name=f"👹 {enemy.name}", value=status, inline=True)

    log_tail = battle.log[-6:]
    if log_tail:
        embed.add_field(name="Battle Log", value="\n".join(log_tail), inline=False)

    if battle.is_over():
        result_text = {
            "won": "🏆 Victory!",
            "lost": "💀 Defeat...",
            "fled": "🏃 Fled the battle.",
        }[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)

    return embed
