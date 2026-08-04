"""
Raid and leaderboard embeds -- the multiplayer views.

Same mobile-width discipline as bot/utils/embedder/combat.py: these are
list-shaped views (a contribution table, a ranked board) and a list that
wraps every row is twice as long and half as readable.
"""

from __future__ import annotations

import discord

from bot.game.economy.raid_config import (
    pool_hp_for,
    CONTRIBUTION_TIERS,
    MAX_ATTACKS_PER_PLAYER,
    contribution_tier,
    get_tier,
)
from bot.utils.embedder._shared import _bar, fit_field

MEDALS = ["🥇", "🥈", "🥉"]


def _short_num(value: float) -> str:
    value = round(value)
    if value < 10_000:
        return str(int(value))
    if value < 1_000_000:
        return f"{value / 1000:.1f}k"
    return f"{value / 1_000_000:.2f}M"


def raid_menu_embed(available_tiers: list[dict], roster_levels: int) -> discord.Embed:
    """Shown when the server has NO active raid: what can be summoned,
    and what's still locked."""
    from bot.game.economy.raid_config import RAID_TIERS

    embed = discord.Embed(
        title="🐉 Co-op Raids",
        description=(
            "A raid is a server-wide boss with one shared HP pool. Everyone attacks it "
            f"on their own time (up to {MAX_ATTACKS_PER_PLAYER} attacks each) and rewards "
            "scale with how much damage you personally contributed.\n\n"
            "**No raid is running right now.** Summon one below."
        ),
        color=discord.Color.dark_red(),
    )
    available_ids = {t["id"] for t in available_tiers}
    for tier in RAID_TIERS:
        # pool_hp_for, not a hand-multiplied constant -- the pool formula
        # depends on EXPECTED_PARTICIPANTS and MAX_ATTACKS_PER_PLAYER, and
        # a duplicated number here would quietly start lying to the player
        # the first time either is retuned.
        pool = pool_hp_for(tier)
        if tier["id"] in available_ids:
            value = f"Boss Lv.{tier['boss_level']} · Pool ~{_short_num(pool)} HP"
        else:
            value = f"🔒 Needs {tier['min_roster_levels']} roster levels (you have {roster_levels})"
        embed.add_field(name=f"{tier['emoji']} {tier['name']}", value=value, inline=False)
    return embed


def raid_status_embed(raid, participants: list, viewer_id: int | None = None,
                      attacks_left: int | None = None) -> discord.Embed:
    """The live raid board: shared HP, who's contributed what, and the
    viewer's own standing."""
    tier = get_tier(raid.tier) or {}
    defeated = raid.status == "defeated"

    embed = discord.Embed(
        title=f"{tier.get('emoji', '🐉')} {tier.get('name', 'Raid')} -- {raid.boss_name}",
        color=discord.Color.gold() if defeated else discord.Color.dark_red(),
    )

    fraction = raid.hp_fraction()
    embed.description = (
        f"**{'💀 DEFEATED' if defeated else 'Lv.' + str(raid.boss_level)}**\n"
        f"❤️ {_short_num(raid.current_hp)} / {_short_num(raid.max_hp)}\n"
        f"{_bar(raid.current_hp, raid.max_hp, length=14)}  {fraction * 100:.1f}%"
    )

    total = sum(p.damage_dealt for p in participants) or 1
    if participants:
        lines = []
        for i, p in enumerate(participants[:10]):
            medal = MEDALS[i] if i < len(MEDALS) else f"`{i + 1}.`"
            share = p.damage_dealt / total
            _, label = contribution_tier(share)
            you = " ◀ you" if p.player_id == viewer_id else ""
            name = p.player.username if p.player else str(p.player_id)
            lines.append(
                f"{medal} **{name[:14]}** — {_short_num(p.damage_dealt)} ({share * 100:.0f}%) {label}{you}"
            )
        embed.add_field(name="⚔️ Contributions", value=fit_field(lines), inline=False)
    else:
        embed.add_field(
            name="⚔️ Contributions",
            value="*Nobody has attacked yet. Be the first.*",
            inline=False,
        )

    if attacks_left is not None and not defeated:
        embed.add_field(
            name="Your attacks",
            value=f"{attacks_left} / {MAX_ATTACKS_PER_PLAYER} remaining",
            inline=True,
        )

    if defeated:
        embed.set_footer(text="Raid cleared! Tap Claim to collect your share of the rewards.")
    else:
        embed.set_footer(text="Damage counts whether you win the fight or not.")
    return embed


def raid_attack_result_embed(result: dict) -> discord.Embed:
    """Shown after one attack resolves."""
    raid = result["raid"]
    won = result.get("won")
    embed = discord.Embed(
        title="💥 Raid Attack Complete",
        color=discord.Color.gold() if won else discord.Color.orange(),
    )
    lines = [
        f"{'🏆 You defeated it!' if won else '💀 Your squad fell -- but the damage still counts.'}",
        f"⚔️ Damage dealt: **{_short_num(result['damage_dealt'])}**",
    ]
    if result["damage_applied"] < result["damage_dealt"]:
        lines.append(
            f"*(Only {_short_num(result['damage_applied'])} counted -- someone else finished the boss first.)*"
        )
    lines.append(
        f"❤️ Boss: {_short_num(raid.current_hp)} / {_short_num(raid.max_hp)} "
        f"{_bar(raid.current_hp, raid.max_hp, length=10)}"
    )
    lines.append(f"📊 Your total contribution: **{_short_num(result['participant'].damage_dealt)}**")
    embed.description = "\n".join(lines)

    if result["just_defeated"]:
        embed.add_field(
            name="🏆 RAID DEFEATED!",
            value="You landed the finishing blow! Everyone who contributed can now claim their rewards.",
            inline=False,
        )
    return embed


def raid_claim_embed(result: dict, raid) -> discord.Embed:
    tier = get_tier(raid.tier) or {}
    embed = discord.Embed(
        title=f"🎁 {tier.get('name', 'Raid')} Rewards",
        description=(
            f"{result['label']} — you dealt **{_short_num(result['damage_dealt'])}** damage "
            f"(**{result['share'] * 100:.1f}%** of the total) for a **{result['multiplier']}x** reward."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Received",
        value="\n".join(result["reward_lines"]) or "*Nothing.*",
        inline=False,
    )
    return embed


def raid_tiers_help_embed() -> discord.Embed:
    embed = discord.Embed(title="📊 Raid Reward Tiers", color=discord.Color.blurple())
    lines = [
        f"**{label}** — {minimum * 100:.0f}%+ of total damage → {multiplier}x rewards"
        for minimum, multiplier, label in CONTRIBUTION_TIERS
    ]
    embed.description = "\n".join(lines)
    embed.set_footer(text="Shares are of total damage dealt, so your reward never depends on who else showed up.")
    return embed


# ----------------------------------------------------------------------
# Leaderboards
# ----------------------------------------------------------------------

def leaderboard_embed(data: dict, board_label: str, board_description: str, guild_name: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"{board_label} — {guild_name}",
        description=board_description,
        color=discord.Color.blurple(),
    )

    entries = data["entries"]
    if not entries:
        embed.add_field(
            name="Empty",
            value="Nobody in this server has anything to rank yet. Use `/start` to join in.",
            inline=False,
        )
        return embed

    lines = []
    for e in entries:
        medal = MEDALS[e["rank"] - 1] if e["rank"] <= len(MEDALS) else f"`{e['rank']:>2}.`"
        marker = " ◀ you" if e["player_id"] == data.get("viewer_id") else ""
        lines.append(f"{medal} **{e['name'][:16]}** — {e['display']}{marker}")
    embed.add_field(name="Top players", value=fit_field(lines), inline=False)

    # Someone outside the top 10 still gets told where they stand -- a
    # board that only ever shows the people already winning gives every
    # other player no reason to look at it twice.
    if data["viewer_rank"] and data["viewer_rank"] > len(entries):
        v = data["viewer_entry"]
        embed.add_field(
            name="Your standing",
            value=f"`#{v['rank']}` of {data['total_ranked']} — {v['display']}",
            inline=False,
        )
    return embed
