"""
Constants and small formatting helpers shared by every embed module in this
package.

Kept in its own module rather than in __init__.py so the section modules can
import from it without importing the package's own __init__ (which imports
all of them right back).
"""

from __future__ import annotations

import discord


ROOM_TYPE_EMOJI = {
    "start": "🚪", "combat": "⚔️", "elite": "🔥", "treasure": "💰",
    "merchant": "🛒", "campfire": "🏕️", "story": "📜", "trap": "⚠️",
    "shrine": "⛩️", "puzzle": "🧩", "secret": "❓", "boss": "💀",
}

RARITY_COLORS = {
    "common": discord.Color.light_grey(),
    "uncommon": discord.Color.green(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.orange(),
    "mythic": discord.Color.red(),
    "divine": discord.Color.gold(),
}

RARITY_EMOJI = {
    "common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣",
    "legendary": "🟠", "mythic": "🔴", "divine": "🟡",
}

STAT_EMOJI = {
    "attack": "⚔️", "defense": "🛡️", "elemental": "🔮", "speed": "💨",
    "max_hp": "❤️", "max_mana": "💧", "crit_rate": "🎯", "crit_damage": "💥",
    "recharge": "🔋",
}

STAT_LABEL = {
    "attack": "ATK", "defense": "DEF", "elemental": "ELE", "speed": "SPD",
    "max_hp": "HP", "max_mana": "SP", "crit_rate": "Crit Rate",
    "crit_damage": "Crit DMG", "recharge": "Recharge",
}

PERCENT_STATS = {"crit_rate", "crit_damage"}


def _fmt_stat(stat: str, value: float) -> str:
    suffix = "%" if stat in PERCENT_STATS else ""
    label = STAT_LABEL.get(stat, stat.replace("_", " ").title())
    return f"{STAT_EMOJI.get(stat, '')} **{label}**: {value:g}{suffix}"


def _fmt_stat_with_base(stat: str, effective_value: float, base_value: float) -> str:
    """'HP: (100) 150' -- base value in parentheses, effective value (with
    gear) alongside it. Falls back to the plain form when gear hasn't
    changed the stat at all, so an unequipped character's page doesn't show
    a redundant '(100) 100' everywhere."""
    if round(base_value, 2) == round(effective_value, 2):
        return _fmt_stat(stat, effective_value)
    suffix = "%" if stat in PERCENT_STATS else ""
    label = STAT_LABEL.get(stat, stat.replace("_", " ").title())
    return f"{STAT_EMOJI.get(stat, '')} **{label}**: ({base_value:g}{suffix}) {effective_value:g}{suffix}"


def _bar(current: float, maximum: float, length: int = 10, fill: str = "█", empty: str = "░") -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = max(0, min(length, round(length * current / maximum)))
    return fill * filled + empty * (length - filled)
