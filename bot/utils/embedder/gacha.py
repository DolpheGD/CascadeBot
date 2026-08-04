"""
Character gacha embeds.

/pull results and the /pull_rates odds table.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
)


# ----------------------------------------------------------------------
# Character gacha
# ----------------------------------------------------------------------

STAR_EMOJI = {3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


def gacha_pull_embed(results: list[dict], player=None) -> discord.Embed:
    """`results` is the list of per-pull dicts returned by
    character_gacha_service (template/is_new/dupe_reward/from_pity).

    `player` is optional and only used to append the post-pull pity
    status -- passing it lets the player see how close the next
    guarantee is without opening /pull_rates separately, which is the
    single most-wanted piece of information right after a pull."""
    multi = len(results) > 1
    embed = discord.Embed(
        title="🎰 Gacha Results" if multi else "🎰 Gacha Result",
        color=discord.Color.gold(),
    )

    # Best pull first so a 10-pull doesn't bury its highlight at the bottom.
    ordered = sorted(results, key=lambda r: (-r["template"].star_rating, not r["is_new"]))

    lines = []
    for r in ordered:
        template = r["template"]
        stars = STAR_EMOJI.get(template.star_rating, "⭐" * template.star_rating)
        class_label = CLASS_DISPLAY_NAME[template.character_class]
        if r["is_new"]:
            tag = "**NEW!**"
        else:
            reward = r["dupe_reward"] or {}
            reward_text = ", ".join(f"+{v} {k.replace('_', ' ')}" for k, v in reward.items())
            tag = f"Duplicate ({reward_text})"
        pity_tag = " 🎟️ *guaranteed*" if r.get("from_pity") else ""
        lines.append(f"{stars} **{template.name}** ({class_label}) -- {tag}{pity_tag}")

    # Discord field values cap at 1024 chars -- chunk a big 10-pull if needed.
    chunk, chunks, length = [], [], 0
    for line in lines:
        if length + len(line) + 1 > 1000:
            chunks.append("\n".join(chunk))
            chunk, length = [], 0
        chunk.append(line)
        length += len(line) + 1
    if chunk:
        chunks.append("\n".join(chunk))

    for i, text in enumerate(chunks):
        embed.add_field(name="Pulled" if i == 0 else "\u200b", value=text, inline=False)

    if player is not None:
        embed.add_field(name="🎟️ Pity", value=_pity_status_lines(player), inline=False)

    new_count = sum(1 for r in results if r["is_new"])
    if multi:
        embed.set_footer(text=f"{new_count}/{len(results)} new characters. Use /squad to update your active team.")
    else:
        embed.set_footer(text="Use /squad to bring your new character on expeditions.")
    return embed


def _pity_status_lines(player) -> str:
    """How far each pity counter has to go, phrased as pulls REMAINING
    rather than pulls accumulated -- "8 pulls to a guaranteed 5★" is the
    question a player actually has, and making them subtract from a
    threshold to get it is needless friction."""
    from bot.game.economy.character_gacha_config import (
        FIVE_STAR_HARD_PITY,
        FIVE_STAR_SOFT_PITY_START,
        FOUR_STAR_PITY,
        five_star_chance_percent,
    )

    five_left = max(0, FIVE_STAR_HARD_PITY - player.pity_since_five_star)
    four_left = max(0, FOUR_STAR_PITY - player.pity_since_four_star)
    current_rate = five_star_chance_percent(player.pity_since_five_star)

    lines = [
        f"⭐⭐⭐⭐⭐ guaranteed in **{five_left}** pull{'s' if five_left != 1 else ''} "
        f"({player.pity_since_five_star}/{FIVE_STAR_HARD_PITY})",
        f"⭐⭐⭐⭐ guaranteed in **{four_left}** pull{'s' if four_left != 1 else ''} "
        f"({player.pity_since_four_star}/{FOUR_STAR_PITY})",
    ]
    if player.pity_since_five_star + 1 > FIVE_STAR_SOFT_PITY_START:
        lines.append(f"🔥 Soft pity active -- next pull is **{current_rate:.0f}%** for a 5★.")
    else:
        soft_left = FIVE_STAR_SOFT_PITY_START - player.pity_since_five_star
        lines.append(f"Soft pity (rising odds) starts in {soft_left} pull{'s' if soft_left != 1 else ''}.")
    return "\n".join(lines)


def gacha_rates_embed(player=None) -> discord.Embed:
    """The /pull_rates odds table. `player` is optional -- when given,
    the player's own live pity progress is shown alongside the static
    rates, since "what are the odds" and "where am I in the cycle" are
    really one question once pity exists."""
    from bot.game.economy.character_gacha_config import (
        FIVE_STAR_HARD_PITY,
        FIVE_STAR_SOFT_PITY_START,
        FIVE_STAR_SOFT_PITY_STEP,
        FOUR_STAR_PITY,
        MULTI_PULL_COST_SHARDS,
        SINGLE_PULL_COST_SHARDS,
        STAR_WEIGHTS,
    )

    total = sum(STAR_WEIGHTS.values())
    embed = discord.Embed(title="🎰 Gacha Rates", color=discord.Color.gold())
    lines = [
        f"{STAR_EMOJI[star]}: {weight / total * 100:.1f}%"
        for star, weight in sorted(STAR_WEIGHTS.items(), reverse=True)
    ]
    embed.add_field(name="Base Odds by Star Rating", value="\n".join(lines), inline=False)

    embed.add_field(
        name="🎟️ Pity (guarantees)",
        value=(
            f"• **Hard pity:** a 5★ is guaranteed on pull **{FIVE_STAR_HARD_PITY}** of a cycle.\n"
            f"• **Soft pity:** from pull **{FIVE_STAR_SOFT_PITY_START}** onward, the 5★ rate climbs "
            f"+{FIVE_STAR_SOFT_PITY_STEP:g}% per pull -- most 5★s land before the hard cap.\n"
            f"• **4★ guarantee:** a 4★ or better every **{FOUR_STAR_PITY}** pulls.\n"
            "• Pulling a 5★ resets both counters. A 10x pull counts as ten separate pulls."
        ),
        inline=False,
    )

    if player is not None:
        embed.add_field(name="Your progress", value=_pity_status_lines(player), inline=False)

    embed.add_field(
        name="Cost",
        value=f"Single pull: {SINGLE_PULL_COST_SHARDS} 💎 Shards\n10x pull: {MULTI_PULL_COST_SHARDS} 💎 Shards (10% off)",
        inline=False,
    )
    embed.add_field(
        name="Duplicates",
        value="Pulling a character you already own converts to gold + reroll tokens instead of a second copy.",
        inline=False,
    )
    embed.set_footer(text="Only characters drop from the gacha -- gear comes from dungeon runs and lootboxes.")
    return embed
