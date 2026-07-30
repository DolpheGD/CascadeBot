"""
Voting embeds.

/vote -- the top.gg vote prompt (what you'd get, and the link to go do it)
and the post-claim reward summary.
"""

from __future__ import annotations

import datetime as dt

import discord

from bot.database.models.enums import MATERIAL_EMOJI, MaterialType
from bot.services.currency_service import format_currency

VOTE_COLOR = discord.Color.from_rgb(255, 115, 250)  # top.gg brand pink-ish


def _material_line(materials: dict[str, int]) -> str:
    emoji_by_value = {m.value: MATERIAL_EMOJI[m] for m in MaterialType}
    return ", ".join(
        f"{amount} {emoji_by_value.get(material, '')}".strip()
        for material, amount in materials.items()
    )


def _lootbox_line(tiers: list[str]) -> str:
    counts: dict[str, int] = {}
    for tier in tiers:
        counts[tier] = counts.get(tier, 0) + 1
    return ", ".join(f"{count}x {tier.title()} Lootbox" for tier, count in counts.items())


def _reward_lines(reward: dict) -> str:
    lines = [
        f"💎 **{format_currency('shards', reward['shards'])}**",
        f"🪙 {format_currency('gold', reward['gold'])}",
        f"🎲 {format_currency('reroll_tokens', reward['reroll_tokens'])}",
    ]
    materials = _material_line(reward["materials"])
    if materials:
        lines.append(f"⛏️ {materials}")
    boxes = _lootbox_line(reward["lootbox_tiers"])
    if boxes:
        lines.append(f"📦 {boxes}")
    return "\n".join(lines)


def vote_prompt_embed(
    reward: dict,
    url: str,
    player,
    cooldown_remaining: dt.timedelta | None = None,
    streak_expires_at: dt.datetime | None = None,
) -> discord.Embed:
    """Shown when the player hasn't voted yet this window (or has already
    claimed). `reward` is vote_service.peek_next_reward() -- the payout
    their NEXT claim would produce, so the ask is concrete rather than a
    vague 'vote for rewards!'."""
    if cooldown_remaining is not None:
        # Discord renders <t:...:R> as a live-updating "in 4 hours".
        ready_at = int((dt.datetime.now(dt.timezone.utc) + cooldown_remaining).timestamp())
        description = (
            f"You've already claimed this vote. You can vote again "
            f"<t:{ready_at}:R>."
        )
    else:
        description = (
            "Vote for CascadeBot on top.gg, then run `/vote` again to claim. "
            "You can vote once every 12 hours."
        )

    embed = discord.Embed(title="🗳️ Vote for CascadeBot", description=description, color=VOTE_COLOR)

    heading = (
        f"Your next vote (streak {reward['streak']})"
        if player.vote_streak
        else "Your first vote"
    )
    embed.add_field(name=heading, value=_reward_lines(reward), inline=False)

    footer_bits = []
    if player.vote_streak:
        footer_bits.append(f"Streak: {player.vote_streak}")
    if player.total_votes:
        footer_bits.append(f"Total votes: {player.total_votes}")
    footer_bits.append(f"Milestone bonus in {reward['milestone_in']} more vote(s)")
    embed.set_footer(text=" | ".join(footer_bits))

    if streak_expires_at is not None and player.vote_streak:
        embed.add_field(
            name="⏳ Keep your streak",
            value=f"Claim again before <t:{int(streak_expires_at.timestamp())}:R> or it resets to 1.",
            inline=False,
        )

    embed.url = url
    return embed


def vote_claimed_embed(result: dict, player) -> discord.Embed:
    """Post-claim summary. `result` is vote_service.claim_vote()'s return."""
    title = "🗳️ Thanks for voting!"
    if result["is_weekend"]:
        title += " (2x weekend!)"

    embed = discord.Embed(
        title=title,
        description=(
            f"Vote streak: **{result['streak']}** "
            f"({result['total_votes']} total vote{'s' if result['total_votes'] != 1 else ''})"
        ),
        color=VOTE_COLOR,
    )
    embed.add_field(name="Rewards", value=_reward_lines(result), inline=False)

    if result["is_weekend"]:
        embed.add_field(
            name="🎉 Weekend multiplier",
            value="Top.gg is running a double-vote weekend -- your Shards and gold were doubled.",
            inline=False,
        )

    embed.set_footer(
        text=f"Vote again in 12 hours | Milestone bonus in {result['milestone_in']} more vote(s)"
    )
    return embed


def vote_unconfigured_embed() -> discord.Embed:
    """Shown when TOPGG_TOKEN isn't set -- /vote still exists so the
    command list doesn't change between deployments, it just explains
    itself instead of erroring."""
    return discord.Embed(
        title="🗳️ Voting isn't set up",
        description=(
            "This instance of CascadeBot doesn't have top.gg voting configured yet. "
            "If you run this bot, set `TOPGG_TOKEN` in your `.env` -- see the README."
        ),
        color=discord.Color.dark_grey(),
    )
