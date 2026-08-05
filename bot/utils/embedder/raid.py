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
    attacks_per_player,
    contribution_tier,
    get_tier,
    lootbox_for,
    rewards_for,
)
from bot.utils.embedder._shared import _bar, fit_field
from bot.services.currency_service import currency_emoji
from bot.utils.names import shorten

MEDALS = ["🥇", "🥈", "🥉"]

# Contribution and leaderboard rows used to hard-cut names at 14 and 16
# characters, which for Discord usernames (up to 32) meant most of the
# table was people the reader could not identify. These rows carry a
# name and one short value, so they can afford the width -- and a
# leaderboard whose whole purpose is "who did this" cannot be the place
# that hides who did it.
PLAYER_NAME_BUDGET = 24

# Reward lines use currency_service.currency_emoji rather than a local
# table. This module used to keep its own copy, and it had already
# drifted: it showed Crystal as 💠 where the rest of the game shows 💎,
# so the same reward rendered differently depending on which screen you
# read it on. One definition per currency, or they diverge.


def _short_num(value: float) -> str:
    value = round(value)
    if value < 10_000:
        return str(int(value))
    if value < 1_000_000:
        return f"{value / 1000:.1f}k"
    return f"{value / 1_000_000:.2f}M"


def reward_line(tier: dict, multiplier: float = 1.0) -> str:
    """One compact line of everything a payout at `multiplier` contains.

    Goes through rewards_for/lootbox_for rather than reading tier
    ["rewards"] directly, so what the player is shown is computed by the
    exact same functions that later grant it."""
    parts = [
        f"{currency_emoji(currency) or '•'} {amount:,}"
        for currency, amount in rewards_for(tier, multiplier).items()
    ]
    box = lootbox_for(tier, multiplier)
    if box:
        parts.append(f"🎁 {box[1]}× {box[0]}")
    return " · ".join(parts) or "*Nothing.*"


def raid_menu_embed(available_tiers: list[dict], roster_levels: int) -> discord.Embed:
    """Shown when the server has NO active raid: what can be summoned,
    and what's still locked."""
    from bot.game.economy.raid_config import RAID_TIERS

    embed = discord.Embed(
        title="🐉 Co-op Raids",
        description=(
            "A raid is a server-wide boss with one shared HP pool. Everyone attacks it "
            "on their own time and rewards scale with how much damage you personally "
            "contributed.\n\n"
            "**No raid is running right now.** Summon one below."
        ),
        color=discord.Color.dark_red(),
    )
    available_ids = {t["id"] for t in available_tiers}
    for tier in RAID_TIERS:
        # pool_hp_for and attacks_per_player, not hand-multiplied
        # constants -- both are per-tier now, and a duplicated number here
        # would quietly start lying the first time one was retuned.
        pool = pool_hp_for(tier)
        if tier["id"] in available_ids:
            lines = [
                f"Boss Lv.{tier['boss_level']} · Pool ~{_short_num(pool)} HP · "
                f"{attacks_per_player(tier)} attacks each",
            ]
            if tier.get("description"):
                lines.append(f"*{tier['description']}*")
            # The whole point of showing this: a player deciding which raid
            # to summon can see what it pays before committing the server
            # to it for days. Shown at 1.0x with the range spelled out,
            # rather than a single number that's true for nobody.
            lines.append(f"**Pays** {reward_line(tier)}")
            lines.append("*at an even share — up to 2.5× if you top the table.*")
            value = "\n".join(lines)
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
                f"{medal} **{shorten(name, PLAYER_NAME_BUDGET)}** — "
                f"{_short_num(p.damage_dealt)} ({share * 100:.0f}%) {label}{you}"
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
            value=f"{attacks_left} / {attacks_per_player(tier)} remaining",
            inline=True,
        )

    # What the viewer is currently on track to be paid.
    #
    # Contribution SHARE was already displayed, but a share is an abstract
    # number -- "you're on 14%" tells a player nothing about whether to
    # spend another attack. Converting it to the actual pile of loot at
    # their current standing is what makes the contribution table
    # something to compete on rather than a statistic to scroll past.
    if tier:
        viewer = next((p for p in participants if p.player_id == viewer_id), None)
        if viewer is not None and viewer.damage_dealt > 0:
            multiplier, label = contribution_tier(viewer.damage_dealt / total)
            embed.add_field(
                name=f"🎁 Your reward at this rate — {label} ({multiplier}×)",
                value=reward_line(tier, multiplier),
                inline=False,
            )
        else:
            floor_multiplier = CONTRIBUTION_TIERS[-1][1]
            embed.add_field(
                name="🎁 Rewards",
                value=(
                    f"{reward_line(tier, floor_multiplier)}\n"
                    "*for turning up at all — more the harder you hit.*"
                ),
                inline=False,
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
    difficulty = result.get("difficulty")
    lines = [
        f"{'🏆 You defeated it!' if won else '💀 Your squad fell -- but the damage still counts.'}",
    ]
    # Show the raw -> credited conversion when a difficulty multiplier is
    # actually doing something. Hiding it would make the contribution
    # number look wrong relative to the damage the log just showed.
    if difficulty and difficulty["contribution_multiplier"] != 1.0:
        lines.append(
            f"{difficulty['emoji']} {difficulty['name']}: "
            f"{_short_num(result.get('raw_damage', 0))} damage × "
            f"{difficulty['contribution_multiplier']} = **{_short_num(result['damage_dealt'])}** credited"
        )
    else:
        lines.append(f"⚔️ Damage dealt: **{_short_num(result['damage_dealt'])}**")
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

    # The payout this attack has earned so far. Shown after every attack,
    # not just at the end: a raid runs for days, and a contribution number
    # with no reward attached gives a player nothing to feel until the
    # boss finally dies -- which may be long after they stopped caring.
    tier = get_tier(raid.tier)
    if tier:
        total = sum(p.damage_dealt for p in raid.participants) or 1
        multiplier, label = contribution_tier(result["participant"].damage_dealt / total)
        embed.add_field(
            name=f"🎁 On track for — {label} ({multiplier}×)",
            value=reward_line(tier, multiplier),
            inline=False,
        )

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


def raid_tiers_help_embed(tier: dict | None = None) -> discord.Embed:
    """The reward table. Given the raid's tier it shows the ACTUAL payout
    at each band rather than a bare multiplier -- "1.5x rewards" is not
    something a player can act on without knowing what 1x was."""
    embed = discord.Embed(title="📊 Raid Reward Tiers", color=discord.Color.blurple())

    if tier is None:
        embed.description = "\n".join(
            f"**{label}** — {minimum * 100:.0f}%+ of total damage → {multiplier}× rewards"
            for minimum, multiplier, label in CONTRIBUTION_TIERS
        )
    else:
        embed.description = f"{tier['emoji']} **{tier['name']}** — what each band pays:"
        for minimum, multiplier, label in CONTRIBUTION_TIERS:
            embed.add_field(
                name=f"{label} — {minimum * 100:.0f}%+ of damage ({multiplier}×)",
                value=reward_line(tier, multiplier),
                inline=False,
            )

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
        lines.append(f"{medal} **{shorten(e['name'], PLAYER_NAME_BUDGET)}** — {e['display']}{marker}")
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
