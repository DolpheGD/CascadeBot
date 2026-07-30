"""
Domains embeds.

/domains -- energy-gated single-battle challenges.
"""

from __future__ import annotations

import discord

from bot.services import domain_service
from bot.game.economy.domain_config import DOMAIN_DIFFICULTY_TIERS, DOMAIN_TYPES, MAX_DOMAIN_ENERGY
from bot.services.currency_service import format_currency
from bot.utils.embedder._shared import _bar


# ----------------------------------------------------------------------
# Domains (/domains) -- energy-gated single-battle challenges against a
# fixed enemy squad, for direct on-demand rewards. See
# bot/services/domain_service.py and bot/game/economy/domain_config.py.
# ----------------------------------------------------------------------

def _energy_bar_line(player) -> str:
    current = domain_service.get_current_energy(player)
    bar = _bar(current, MAX_DOMAIN_ENERGY, length=12)
    line = f"⚡ {current}/{MAX_DOMAIN_ENERGY} {bar}"
    next_point = domain_service.time_until_next_energy_point(player)
    if next_point is not None:
        minutes = int(next_point.total_seconds() // 60) + 1
        line += f"\n*Next point in {minutes}m*"
    return line


def domain_menu_embed(player) -> discord.Embed:
    """Top-level /domains screen: energy status + every domain type."""
    embed = discord.Embed(title="🌀 Domains", color=discord.Color.dark_purple())
    embed.add_field(name="Energy", value=_energy_bar_line(player), inline=False)
    for domain in DOMAIN_TYPES:
        embed.add_field(name=f"{domain['icon']} {domain['name']}", value=domain["description"], inline=False)
    embed.set_footer(text="Pick a domain below to see its difficulty tiers.")
    return embed


def domain_tier_embed(domain: dict, player) -> discord.Embed:
    """Shown after picking a domain type: energy status + every
    difficulty tier for THIS domain, with its reward, level requirement,
    and energy cost. Locked-by-level tiers are still shown (so the player
    can see what's coming) but marked accordingly -- affordability is
    conveyed by the tier buttons themselves, not here."""
    embed = discord.Embed(
        title=f"{domain['icon']} {domain['name']}", description=domain["description"],
        color=discord.Color.dark_purple(),
    )
    embed.add_field(name="Energy", value=_energy_bar_line(player), inline=False)

    for tier in DOMAIN_DIFFICULTY_TIERS:
        reward = domain["rewards"][tier["id"]]
        if domain["reward_kind"] == "currency":
            reward_text = ", ".join(format_currency(c, a) for c, a in reward.items())
        elif domain["reward_kind"] == "lootbox":
            lootbox_tier, quantity = reward
            reward_text = f"{quantity}x {lootbox_tier.title()} Lootbox"
        else:
            reward_text = f"{reward} XP (split across squad)"

        if player.level < tier["min_player_level"]:
            name = f"🔒 {tier['name']} -- requires level {tier['min_player_level']}"
        else:
            name = f"{tier['name']} -- {tier['energy_cost']} ⚡"
        embed.add_field(name=name, value=reward_text, inline=True)

    return embed


def domain_result_embed(result: dict) -> discord.Embed:
    """Shown once a domain battle ends -- see domain_service.resolve_challenge."""
    domain, tier = result["domain"], result["tier"]
    if result["won"]:
        title = f"✅ {tier['name']} {domain['name']} cleared!"
        color = discord.Color.green()
        body = "\n".join(result["reward_lines"]) if result["reward_lines"] else "*Nothing this time.*"
    else:
        title = f"💀 {tier['name']} {domain['name']} failed"
        color = discord.Color.red()
        body = "No reward this attempt -- the energy spent isn't refunded, but nothing else is lost. Try a lower tier, or gear up and come back."
    embed = discord.Embed(title=title, description=body, color=color)
    return embed
